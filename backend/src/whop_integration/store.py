"""Durable local order ledger and webhook inbox. No payment/card payload storage."""
from contextlib import contextmanager
import hashlib,json,sqlite3,time
from pathlib import Path

class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS orders (
              id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, environment TEXT NOT NULL,
              company_id TEXT NOT NULL, product_id TEXT NOT NULL, plan_id TEXT NOT NULL,
              amount TEXT NOT NULL, currency TEXT NOT NULL, status TEXT NOT NULL,
              checkout_id TEXT UNIQUE, checkout_url TEXT, payment_id TEXT UNIQUE,
              user_id TEXT, verified_at REAL, created_at REAL NOT NULL,
              fulfillment_status TEXT NOT NULL DEFAULT 'not_started');
            CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY, body_hash TEXT NOT NULL, type TEXT NOT NULL,
              payment_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
              attempts INTEGER NOT NULL DEFAULT 0, available_at REAL NOT NULL DEFAULT 0,
              lease_until REAL NOT NULL DEFAULT 0, last_error TEXT);
            CREATE TABLE IF NOT EXISTS research_jobs (
              id TEXT PRIMARY KEY, order_id TEXT UNIQUE NOT NULL REFERENCES orders(id),
              brief_json TEXT NOT NULL, fields_json TEXT NOT NULL, source_json TEXT NOT NULL,
              input_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'awaiting_research',
              created_at REAL NOT NULL);
            ''')
            columns={row['name'] for row in db.execute('PRAGMA table_info(research_jobs)')}
            for name,kind in [('run_id','TEXT'),('started_at','REAL'),('finished_at','REAL'),('last_error','TEXT')]:
                if name not in columns:db.execute(f'ALTER TABLE research_jobs ADD COLUMN {name} {kind}')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=5);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def create_order(self,oid,token,config):
        with self.connect() as db:
            db.execute('INSERT INTO orders(id,token_hash,environment,company_id,product_id,plan_id,amount,currency,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (oid,hashlib.sha256(token.encode()).hexdigest(),config.environment,config.company_id,config.product_id,config.plan_id,config.price,config.currency,'creating_checkout',time.time()))

    def order(self,oid):
        with self.connect() as db:
            row=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            return dict(row) if row else None

    def bind_checkout(self,oid,checkout_id,url):
        with self.connect() as db:db.execute("UPDATE orders SET checkout_id=?,checkout_url=?,status='awaiting_payment' WHERE id=?",(checkout_id,url,oid))

    def checkout_failed(self,oid):
        with self.connect() as db:db.execute("UPDATE orders SET status='checkout_error' WHERE id=? AND status='creating_checkout'",(oid,))

    def enqueue(self,event,body,payment_id):
        digest=hashlib.sha256(body).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT body_hash FROM events WHERE id=?',(event['id'],)).fetchone()
            if prior:
                if prior['body_hash']!=digest:raise ValueError('Conflicting webhook event ID')
                return False
            db.execute('INSERT INTO events(id,body_hash,type,payment_id) VALUES(?,?,?,?)',(event['id'],digest,event['type'],payment_id))
            return True

    def claim(self,*,now=None):
        now=time.time() if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM events WHERE (status='pending' AND available_at<=?) OR (status='processing' AND lease_until<?) ORDER BY rowid LIMIT 1",(now,now)).fetchone()
            if not row:return None
            db.execute("UPDATE events SET status='processing',lease_until=?,attempts=attempts+1 WHERE id=?",(now+60,row['id']))
            return dict(row)

    def retry(self,event_id,category):
        with self.connect() as db:
            db.execute("UPDATE events SET status='pending',available_at=?,lease_until=0,last_error=? WHERE id=?",(time.time()+30,category,event_id))

    def apply(self,event_id,payment,config,validator):
        """Remote current state -> order update and event completion in one transaction."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            metadata=payment.get('metadata') or {}
            oid=metadata.get('research_order_id') if isinstance(metadata,dict) else None
            row=db.execute('SELECT * FROM orders WHERE id=? OR payment_id=?',(oid,payment.get('id'))).fetchone()
            if row:
                order=dict(row)
                result=validator(order,payment,config)
                # Reversals are terminal in phase 1; no stale delivery can regrant access.
                if order['status']=='revoked' and result=='paid':result='revoked'
                if result in {'paid','revoked'}:
                    db.execute('UPDATE orders SET status=?,payment_id=?,user_id=?,verified_at=? WHERE id=?',
                        (result,payment['id'],(payment.get('user') or {}).get('id'),time.time(),order['id']))
                    if result=='revoked':
                        db.execute("UPDATE orders SET fulfillment_status='payment_revoked' WHERE id=?",(order['id'],))
                        db.execute("UPDATE research_jobs SET status='payment_revoked' WHERE order_id=?",(order['id'],))
                db.execute("UPDATE events SET status='done',lease_until=0,last_error=? WHERE id=?",(None if result=='paid' else result,event_id))
                return result
            db.execute("UPDATE events SET status='done',lease_until=0,last_error='unrelated_payment' WHERE id=?",(event_id,))
            return 'unrelated_payment'

    def submit_intake(self,oid,prepared,source):
        from .intake import IntakeConflict
        data=json.dumps({'brief':prepared['brief'],'fields':prepared['fields'],'source':source},sort_keys=True,allow_nan=False)
        digest=hashlib.sha256(data.encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            order=db.execute('SELECT status FROM orders WHERE id=?',(oid,)).fetchone()
            if not order or order['status']!='paid':raise PermissionError('Verified payment required')
            existing=db.execute('SELECT id,input_hash,status FROM research_jobs WHERE order_id=?',(oid,)).fetchone()
            if existing:
                if existing['input_hash']!=digest:raise IntakeConflict('This order already has a different submitted brief')
                return {'job_id':existing['id'],'status':existing['status'],'duplicate':True}
            job_id='job_'+oid
            db.execute('INSERT INTO research_jobs(id,order_id,brief_json,fields_json,source_json,input_hash,created_at) VALUES(?,?,?,?,?,?,?)',
                (job_id,oid,json.dumps(prepared['brief']),json.dumps(prepared['fields']),json.dumps(source),digest,time.time()))
            db.execute("UPDATE orders SET fulfillment_status='awaiting_research' WHERE id=?",(oid,))
            return {'job_id':job_id,'status':'awaiting_research','duplicate':False}

    def intake_job(self,oid):
        with self.connect() as db:
            row=db.execute('SELECT id,status,brief_json,fields_json,created_at FROM research_jobs WHERE order_id=?',(oid,)).fetchone()
            return {'job_id':row['id'],'status':row['status'],'brief':json.loads(row['brief_json']),'fields':json.loads(row['fields_json'])} if row else None

    def claim_research(self,environment):
        """Claim once, without automatic crash retries that could repeat model spend."""
        import secrets
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT j.* FROM research_jobs j JOIN orders o ON o.id=j.order_id WHERE j.status='awaiting_research' AND o.status='paid' AND o.environment=? ORDER BY j.created_at LIMIT 1",(environment,)).fetchone()
            if not row:return None
            run_id='whop-'+secrets.token_hex(16)
            db.execute("UPDATE research_jobs SET status='processing',run_id=?,started_at=? WHERE id=?",(run_id,time.time(),row['id']))
            db.execute("UPDATE orders SET fulfillment_status='processing' WHERE id=?",(row['order_id'],))
            return {**dict(row),'status':'processing','run_id':run_id}

    def finish_research(self,job_id,status,error=None):
        if status not in {'completed','needs_attention','failed'}:raise ValueError('Invalid research result')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT j.order_id,j.status,o.status AS payment_status FROM research_jobs j JOIN orders o ON o.id=j.order_id WHERE j.id=?",(job_id,)).fetchone()
            if not row or row['status']!='processing' or row['payment_status']!='paid':return False
            db.execute('UPDATE research_jobs SET status=?,last_error=?,finished_at=? WHERE id=?',(status,error,time.time(),job_id))
            db.execute('UPDATE orders SET fulfillment_status=? WHERE id=?',(status,row['order_id']))
            return True

    def verify_current_order(self,oid,payment,config,validator):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            if not row:return False
            order=dict(row);result=validator(order,payment,config)
            if payment.get('id')!=order['payment_id']:return False
            if order['status']=='revoked':return False
            if result=='revoked':
                db.execute("UPDATE orders SET status='revoked',fulfillment_status='payment_revoked',verified_at=? WHERE id=?",(time.time(),oid))
                db.execute("UPDATE research_jobs SET status='payment_revoked' WHERE order_id=?",(oid,))
            elif result=='paid':db.execute('UPDATE orders SET verified_at=? WHERE id=?',(time.time(),oid))
            return result=='paid'

    def research_job(self,oid):
        with self.connect() as db:
            row=db.execute('SELECT * FROM research_jobs WHERE order_id=?',(oid,)).fetchone()
            return dict(row) if row else None

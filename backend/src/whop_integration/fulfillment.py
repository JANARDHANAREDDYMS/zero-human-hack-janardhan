"""Paid generation execution and private research reports, no simulation yet."""
import hashlib,html,json,re
from pathlib import Path
from collections import Counter
from customer_generation.approval import write_summary,summary_lines
from customer_generation.pipeline import run_generation
from customer_generation.state import RunLimits
from .service import verify_payment

ROOT=Path(__file__).resolve().parents[3]

class Fulfillment:
    def __init__(self,service,run_root=None,backend_factory=None,generator=run_generation):
        self.service=service;self.root=Path(run_root or ROOT/'data/runs')
        self.backend_factory=backend_factory;self.generator=generator

    def eligible(self,oid):
        order=self.service.store.order(oid)
        if not order or order['status']!='paid' or order['environment']!=self.service.config.environment or not order['payment_id']:return False
        payment=self.service.client.payment(order['payment_id'])
        return self.service.store.verify_current_order(oid,payment,self.service.config,verify_payment)

    def process_once(self):
        job=self.service.store.claim_research(self.service.config.environment)
        if not job:return {'processed':False}
        try:
            if not self.eligible(job['order_id']):
                self.service.store.finish_research(job['id'],'needs_attention','payment_not_eligible')
                return {'processed':True,'status':'payment_not_eligible'}
            if self.backend_factory is None:
                from customer_generation.config import AdapterConfig
                from customer_generation.tools.live import LiveBackend
                backend=LiveBackend(AdapterConfig.from_environment(backend='bridge'),proposal_format='compact')
            else:backend=self.backend_factory()
            state=self.generator(json.loads(job['brief_json']),backend,self.root,job['run_id'],target_count=50,seed=42,
                limits=RunLimits(max_tokens_per_call=40000,max_total_tokens=160000,max_cost_usd=1))
            status='needs_attention'
            if state.status=='completed':
                folder=self.root/job['run_id'];write_summary(folder)
                manifest={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ['customers.json','specification.json','evidence.json','brief.json']}
                (folder/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
                if not self.eligible(job['order_id']):
                    self.service.store.finish_research(job['id'],'needs_attention','payment_not_eligible')
                    return {'processed':True,'status':'payment_not_eligible'}
                status='completed'
            published=self.service.store.finish_research(job['id'],status,None if status=='completed' else 'generation_incomplete')
            return {'processed':True,'status':status if published else 'access_revoked'}
        except Exception:
            self.service.store.finish_research(job['id'],'failed','fulfillment_failed')
            return {'processed':True,'status':'failed','note':'No automatic retry; inspect saved run locally.'}

    def result(self,oid,token,part=None):
        status=self.service.status(oid,token)
        if not status:raise LookupError('Order not found')
        if not status['intake_unlocked'] or status['environment']!=self.service.config.environment:raise PermissionError('Verified payment required')
        job=self.service.store.research_job(oid)
        if not job:return {'status':'awaiting_intake','report_ready':False}
        response={'job_id':job['id'],'status':job['status'],'report_ready':False}
        if job['status']!='completed':return response
        # Fail closed during provider outages or after current refund/reversal.
        if not self.eligible(oid):raise PermissionError('Current verified payment required')
        if not re.fullmatch('whop-[a-f0-9]{32}',job['run_id'] or ''):raise ValueError('Invalid run association')
        folder=self.root/job['run_id']
        names={'customers':'customers.json','evidence':'evidence.json','specification':'specification.json','brief':'brief.json'}
        manifest=json.loads((folder/'delivery-manifest.json').read_text())
        for name in names.values():
            if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=manifest.get(name):raise ValueError('Delivery artifacts changed')
        if part:
            if part not in names:raise LookupError('Result not found')
            return json.loads((folder/names[part]).read_text())
        customers=json.loads((folder/'customers.json').read_text());spec=json.loads((folder/'specification.json').read_text())
        response.update(report_ready=True,summary=summary_lines(folder),count=customers['count'],
            segments=[{'segment_id':s['segment_id'],'name':s['name'],'count':sum(c['segment_id']==s['segment_id'] for c in customers['customers'])} for s in spec['segments']],
            limitations=['Synthetic customer profiles; not real respondents or measured market shares.','Generation completed; human quality approval and customer simulation are separate.'])
        return response

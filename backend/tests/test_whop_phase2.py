"""Paid intake and Markdown parsing; no Whop/model/network calls."""
import json,unittest
from dataclasses import replace
from whop_integration.intake import prepare,markdown_fields,MAX_MARKDOWN,IntakeConflict
from customer_generation.validation import validate_intake
import test_whop_phase1 as phase1

MARKDOWN='''# Product name
Sony demo speaker
## Description
A portable speaker for travel.
## Planned price
119 USD one-time
## Features
- USB-C charging
- Carry strap
## Research question
Which alternatives could customers prefer?
## Audience
Travelers
'''

class PaidIntakeTests(unittest.TestCase):
    setUp=phase1.WhopPhase1Tests.setUp
    tearDown=phase1.WhopPhase1Tests.tearDown
    order_and_payment=phase1.WhopPhase1Tests.order_and_payment
    request=phase1.WhopPhase1Tests.request

    def paid(self):
        oid,token,p=self.order_and_payment()
        with self.store.connect() as db:db.execute("UPDATE orders SET status='paid',payment_id='pay_demo' WHERE id=?",(oid,))
        return oid,token,p

    def test_paid_form_preview_and_one_job(self):
        oid,token,_=self.paid();payload={'fields':{'name':'Sony speaker','description':'A travel speaker'}}
        preview=self.service.intake(oid,token,payload)
        self.assertTrue(preview['can_submit']);self.assertIsNone(preview['brief']['price'])
        self.assertTrue(preview['warnings']);validate_intake(preview['brief'])
        job=self.service.intake(oid,token,payload,submit=True)
        self.assertEqual(job['status'],'awaiting_research')
        self.assertTrue(self.service.intake(oid,token,payload,submit=True)['duplicate'])
        self.assertEqual(self.service.intake(oid,token)['brief'],preview['brief'])
        payload['fields']['description']='Changed after submission'
        with self.assertRaises(IntakeConflict):self.service.intake(oid,token,payload,submit=True)

    def test_markdown_extracts_known_fields_without_guesses(self):
        oid,token,_=self.paid();payload={'filename':'sony.md','markdown':MARKDOWN}
        preview=self.service.intake(oid,token,payload)
        self.assertEqual(preview['brief']['price'],{'amount':119.0,'currency':'USD','billing_period':'one_time'})
        self.assertEqual(preview['brief']['known_features'],{'feature_1':'USB-C charging','feature_2':'Carry strap'})
        self.assertIsNone(preview['brief']['market']);self.assertIsNone(preview['brief']['category'])
        self.assertEqual(preview['fields']['name'],'Sony demo speaker')
        self.service.intake(oid,token,payload,submit=True)
        with self.store.connect() as db:
            row=db.execute('SELECT source_json FROM research_jobs').fetchone()
            self.assertEqual(json.loads(row[0])['text'],MARKDOWN)

    def test_preview_edits_override_upload_and_preserve_source(self):
        oid,token,_=self.paid()
        p=prepare(oid,{'filename':'sony.md','markdown':MARKDOWN,'fields':{'name':'Corrected name','price':''}})
        self.assertEqual(p['brief']['name'],'Corrected name');self.assertIsNone(p['brief']['price'])
        self.assertIn(MARKDOWN,p['brief']['materials'][0]['value'])

    def test_unpaid_and_wrong_token_cannot_preview_submit_or_read(self):
        oid,token,_=self.order_and_payment();payload={'fields':{'name':'A','description':'B'}}
        for submit in [False,True]:
            with self.assertRaises(PermissionError):self.service.intake(oid,token,payload,submit=submit)
        with self.assertRaises(LookupError):self.service.intake(oid,'wrong-token',payload)
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM research_jobs').fetchone()[0],0)

    def test_revoked_payment_locks_existing_job_and_cancels_queue(self):
        oid,token,p=self.paid();payload={'fields':{'name':'A','description':'B'}}
        self.service.intake(oid,token,payload,submit=True)
        event=phase1.WhopPhase1Tests.event(self,event_id='msg_refund',kind='refund.updated')
        raw,h=phase1.signed(event);self.service.receive(raw,h)
        self.client.payment_data={**p,'refunded_amount':9,'substatus':'refunded'}
        self.service.drain_once()
        with self.assertRaises(PermissionError):self.service.intake(oid,token)
        self.assertEqual(self.store.intake_job(oid)['status'],'payment_revoked')

    def test_unknown_markdown_and_ambiguous_price_remain_unknown(self):
        p=prepare('a'*32,{'filename':'notes.md','markdown':'Unstructured plain text about a speaker.'})
        self.assertFalse(p['can_submit']);self.assertEqual(set(p['missing_fields']),{'name','description'})
        p=prepare('a'*32,{'fields':{'name':'A','description':'B','price':'about $100'}})
        self.assertIsNone(p['brief']['price']);self.assertIn('about $100',p['brief']['materials'][0]['value'])

    def test_duplicate_headings_paths_wrong_extension_and_size_rejected(self):
        cases=[('a.md',MARKDOWN+'\n## Description\nDuplicate'),('../a.md',MARKDOWN),('a.txt',MARKDOWN),('a.md','x'*(MAX_MARKDOWN+1)),('a.md','\x00')]
        for filename,text in cases:
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):markdown_fields(filename,text)

    def test_title_heading_and_unrecognized_sections(self):
        fields,warnings=markdown_fields('a.md','# Example Speaker\n\n## Description\nA speaker\n## Something else\nUnknown details')
        self.assertEqual(fields['name'],'Example Speaker');self.assertEqual(fields['description'],'A speaker');self.assertTrue(warnings)

    def test_empty_required_fields_preview_but_submission_rejected(self):
        oid,token,_=self.paid()
        self.assertFalse(self.service.intake(oid,token,{'fields':{}})['can_submit'])
        with self.assertRaises(ValueError):self.service.intake(oid,token,{'fields':{}},submit=True)

    def test_http_paid_preview_submission_and_conflict(self):
        oid,token,_=self.paid();cookie='research_order_token='+token;path='/api/orders/'+oid+'/intake'
        body=json.dumps({'filename':'sony.md','markdown':MARKDOWN}).encode()
        r,d=self.request(path+'/preview','POST',body,cookie=cookie);self.assertEqual(r['status'],200)
        r,d=self.request(path+'/submit','POST',body,cookie=cookie);self.assertEqual(r['status'],201)
        r,d=self.request(path+'/submit','POST',body,cookie=cookie);self.assertEqual(r['status'],200)
        r,d=self.request(path);self.assertEqual(r['status'],404)
        r,d=self.request(path,cookie=cookie);self.assertEqual(r['status'],200);self.assertEqual(d['job']['status'],'awaiting_research')
        body=json.dumps({'fields':{'name':'Changed','description':'Different'}}).encode()
        r,_=self.request(path+'/submit','POST',body,cookie=cookie);self.assertEqual(r['status'],409)

    def test_http_origin_guard_and_unknown_fields(self):
        oid,token,_=self.paid();path='/api/orders/'+oid+'/intake/submit';cookie='research_order_token='+token
        r,_=self.request(path,'POST',b'{"payment_status":"paid"}',cookie=cookie);self.assertEqual(r['status'],400)
        r,_=self.request(path,'POST',b'{}',cookie=cookie,headers={'Origin':'https://evil.example'});self.assertEqual(r['status'],403)

    def test_sandbox_order_cannot_cross_into_production_intake(self):
        oid,token,_=self.paid();self.service.config=replace(self.c,environment='sandbox')
        with self.assertRaises(PermissionError):self.service.intake(oid,token)

    def test_html_and_template_are_served_as_text_not_executed_uploads(self):
        r,html=self.request('/intake');self.assertEqual(r['status'],200);self.assertIn('text/html',r['headers']['Content-Type'])
        self.assertIn('textContent',html);self.assertNotIn('innerHTML',html)
        r,template=self.request('/intake-template.md');self.assertEqual(r['status'],200);self.assertIn('## Description',template)

if __name__=='__main__':unittest.main()

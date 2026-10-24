"""Failure-oriented tests of the generic sampler, not model-quality claims."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from customer_generation import ContractError, generate_population, validate_intake, validate_evidence, validate_specification
from customer_generation.sampling import SamplingExhausted, canonical

FIX=Path(__file__).parent/'fixtures/keyboard'
def load(name):return json.loads((FIX/name).read_text())
def constant(x):return {'kind':'constant','value':x}

class PhaseOneTests(unittest.TestCase):
    def setUp(self):
        self.spec=load('specification.json');self.evidence=load('evidence.json')
    def test_sparse_intake_retains_unknown_optional_fields(self):
        intake=load('intake.json');validate_intake(intake)
        self.assertNotIn('price',intake);self.assertNotIn('audience',intake)
    def test_missing_description_and_blank_question_rejected(self):
        for field,value in [('description',None),('research_question','   ')]:
            intake=load('intake.json');intake[field]=value
            with self.assertRaises(ContractError):validate_intake(intake)
    def test_new_category_two_segments_and_conditional_dependencies(self):
        pop=generate_population(self.spec,self.evidence)
        self.assertEqual(pop['count'],50)
        self.assertEqual(len({p['segment_id'] for p in pop['customers']}),2)
        for p in pop['customers']:
            self.assertEqual(p['budget']['comfortable'],int(.75*p['budget']['maximum']))
            if p['category_context']['work_mode']=='travel':
                width=next(r for r in p['requirements'] if r['attribute']=='width_cm')
                self.assertEqual(width['value'],p['category_context']['bag_width_cm']-2)
    def test_seed_reproducibility_and_input_not_mutated(self):
        before=canonical(self.spec);a=generate_population(self.spec,self.evidence);b=generate_population(self.spec,self.evidence)
        self.assertEqual(canonical(a),canonical(b));self.assertEqual(before,canonical(self.spec))
        self.spec['seed']+=1
        self.assertNotEqual(a['customers'],generate_population(self.spec,self.evidence)['customers'])
    def test_five_hundred_profile_target(self):
        self.spec['target_count']=500
        for segment in self.spec['segments']:segment['count']=250
        self.assertEqual(generate_population(self.spec,self.evidence)['count'],500)
    def test_product_rename_needs_no_new_category_code(self):
        self.spec['product_id']='unseen-device';self.evidence['product_id']='unseen-device'
        self.assertEqual(generate_population(self.spec,self.evidence)['count'],50)
    def test_unknown_field_reference(self):
        self.spec['segments'][0]['fields']['budget.maximum']['rule']={'kind':'reference','field':'category_context.missing'}
        with self.assertRaisesRegex(ContractError,'unknown fields'):validate_specification(self.spec,self.evidence)
    def test_cycle_detected_before_sampling(self):
        self.spec['segments'][0]['fields']['budget.maximum']['rule']={'kind':'reference','field':'budget.comfortable'}
        with self.assertRaisesRegex(ContractError,'Cyclic'):validate_specification(self.spec,self.evidence)
    def test_bad_source_and_assumption_laundering(self):
        rationale=self.spec['segments'][0]['rationale'];rationale['source_ids']=['nonexistent']
        with self.assertRaisesRegex(ContractError,'unknown source'):validate_specification(self.spec,self.evidence)
        rationale['source_ids']=[];rationale['finding_ids']=['guess'];rationale['basis']='market_evidence'
        self.evidence['findings']=[{'finding_id':'guess','subject':'buyers','attribute':'budget','value':50,'unit':'USD','basis':'assumption','source_ids':[],'note':'Invented range.'}]
        with self.assertRaisesRegex(ContractError,'cannot become market evidence'):validate_specification(self.spec,self.evidence)
    def test_provider_claim_needs_source_and_unknown_stays_null(self):
        f={'finding_id':'test','subject':'offer','attribute':'price','value':20,'unit':'USD','basis':'provider_claim','source_ids':[],'note':'Unverified'}
        self.evidence['findings']=[f]
        with self.assertRaisesRegex(ContractError,'requires a source'):validate_evidence(self.evidence)
        f['basis']='unknown'
        with self.assertRaisesRegex(ContractError,'null'):validate_evidence(self.evidence)
    def test_inverted_range_and_wrong_choice_weights(self):
        field=self.spec['segments'][0]['fields']['budget.maximum']
        for rule in [{'kind':'integer','minimum':10,'maximum':2},{'kind':'choice','values':[1,2],'weights':[1]}]:
            field['rule']=rule
            with self.assertRaises(ContractError):validate_specification(self.spec,self.evidence)
    def test_bounded_contradictions(self):
        fields=self.spec['segments'][0]['fields'];fields['budget.maximum']['rule']=constant(10);fields['budget.comfortable']['rule']=constant(20)
        with self.assertRaisesRegex(SamplingExhausted,'within 25 attempts'):
            generate_population(self.spec,self.evidence,max_attempts_per_customer=1)
    def test_declared_cross_field_constraint_enforced(self):
        self.spec['segments'][0]['constraints'].append({'left':'category_context.bag_width_cm','operator':'gte','right':{'value':100},'message':'Carrying space too small.'})
        with self.assertRaisesRegex(SamplingExhausted,'Carrying space too small'):
            generate_population(self.spec,self.evidence,max_attempts_per_customer=1)
    def test_duplicate_segment_and_wrong_allocations(self):
        self.spec['segments'][1]['segment_id']=self.spec['segments'][0]['segment_id']
        with self.assertRaisesRegex(ContractError,'Duplicate segment'):validate_specification(self.spec,self.evidence)
        self.spec=load('specification.json');self.spec['target_count']=49
        with self.assertRaisesRegex(ContractError,'sum'):validate_specification(self.spec,self.evidence)
    def test_insufficient_diversity_fails_instead_of_copying(self):
        self.spec['segments']=self.spec['segments'][:1];self.spec['target_count']=2;s=self.spec['segments'][0];s['count']=2
        p=generate_population(load('specification.json'),self.evidence)['customers'][0]
        from customer_generation.sampling import get_path
        for path,definition in s['fields'].items():definition['rule']=constant(get_path(p,path))
        with self.assertRaisesRegex(SamplingExhausted,'Duplicate profile'):
            generate_population(self.spec,self.evidence,max_attempts_per_customer=2)
    def test_no_arbitrary_code_and_no_outcome_fields(self):
        self.spec['segments'][0]['fields']['budget.maximum']['rule']={'kind':'python','code':'print(1)'}
        with self.assertRaises(ContractError):validate_specification(self.spec,self.evidence)
        self.spec=load('specification.json');self.spec['attributes']['preferred_product']={'type':'string','unit':None,'description':'Predetermined winner'}
        with self.assertRaisesRegex(ContractError,'buying outcomes'):validate_specification(self.spec,self.evidence)
    def test_nonfinite_and_invalid_attribute_types(self):
        self.spec['segments'][0]['fields']['budget.maximum']['rule']=constant(float('nan'))
        with self.assertRaisesRegex(ContractError,'Non-finite'):validate_specification(self.spec,self.evidence)
        self.spec=load('specification.json');self.spec['segments'][0]['requirements'][0]['operator']='gte'
        with self.assertRaisesRegex(ContractError,'numeric attribute'):validate_specification(self.spec,self.evidence)
    def test_field_insertion_order_does_not_change_output(self):
        first=generate_population(self.spec,self.evidence)
        for seg in self.spec['segments']:seg['fields']=dict(reversed(list(seg['fields'].items())))
        second=generate_population(self.spec,self.evidence)
        self.assertEqual(first['customers'],second['customers'])
    def test_cli_cannot_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'customers.json';output.write_text('preserve me')
            r=subprocess.run([sys.executable,'-m','customer_generation','sample','--spec',str(FIX/'specification.json'),'--evidence',str(FIX/'evidence.json'),'--output',str(output)],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0);self.assertEqual(output.read_text(),'preserve me')

if __name__=='__main__':unittest.main()

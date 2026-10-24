#!/usr/bin/env python3
"""Validate saved demo data, schemas, reproducibility, and contract fixtures.
Requires jsonschema, used for local validation only. Never calls a model or network.
"""
import json
import warnings
from pathlib import Path
from generate_populations import ROOT, read, validate, encode

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    from jsonschema import Draft202012Validator, RefResolver, ValidationError

def validator(path):
    s=read(path)
    Draft202012Validator.check_schema(s)
    return Draft202012Validator(s,resolver=RefResolver(path.resolve().as_uri(),s))

def main():
    pv=validator(ROOT/'schemas/population.schema.json')
    cv=validator(ROOT/'schemas/customer.schema.json')
    bv=validator(ROOT/'schemas/product.schema.json')
    reports=[]
    for folder in sorted((ROOT/'products').iterdir()):
        if not folder.is_dir() or not (folder/'customers.json').exists():continue
        bv.validate(read(folder/'brief.json'))
        for name in ['segments.json','sampling-rules.json','customers.json']:
            pv.validate(read(folder/name))
        pop=read(folder/'customers.json')
        for c in pop['customers']:cv.validate(c)
        reports.append(validate(folder,pop))
        pilot=read(ROOT/'simulation/pilots'/f'{folder.name}.json')
        assert pilot['count']==len(pilot['customers'])==5
        for c in pilot['customers']:
            cv.validate(c)
            assert c in pop['customers']
        assert len({c['segment_id'] for c in pilot['customers']})==5
    fixture=read(ROOT/'simulation/sony-example-request.json')
    validator(ROOT/'simulation/request.schema.json').validate(fixture)
    sources={s['source_id'] for s in read(ROOT/'products/sony-speaker/evidence.json')['sources']}
    fact_ids=[]
    for offer in fixture['offers']:
        assert not {'negative_features','standout','selling_point','design_notes'} & set(offer)
        for facts in offer['sections'].values():
            for fact in facts:
                assert fact['source_id'] in sources
                fact_ids.append(fact['fact_id'])
                if fact['evidence_status']=='unknown':assert fact['value'] is None
    assert len(set(fact_ids))==len(fact_ids)
    av=validator(ROOT/'simulation/action.schema.json')
    av.validate({'action':'inspect_offer','offer_id':'sony-concept','section':'features'})
    av.validate({'action':'decide','decision':{'choice':'insufficient_information','offer_id':None,'reason':'Needed evidence is unavailable.','supporting_fact_ids':[],'unresolved_attributes':['delivery_days']}})
    # Guard against malformed contracts accidentally accepting fabricated actions/choices.
    invalid=[{'action':'purchase'}, {'action':'inspect_offer','offer_id':'x','section':'hidden_reasoning'},
      {'action':'decide','decision':{'choice':'select_offer','offer_id':None,'reason':'x','supporting_fact_ids':[],'unresolved_attributes':[]}}]
    for action in invalid:
        try:av.validate(action)
        except ValidationError:pass
        else:raise AssertionError('Invalid action was accepted')
    validator(ROOT/'simulation/result.schema.json')
    report={'status':'passed_structural_and_reproducibility_checks','total_customers':sum(r['count'] for r in reports),'products':reports,'schema_checks':'passed','pilot_checks':'passed','sony_input_fixture':'passed','action_contract_checks':'passed','external_validity':'Not established; no human, behavioral, or runtime model evaluation performed.','runtime_simulator':'Not implemented'}
    (ROOT/'simulation/population-validation.json').write_text(encode(report))
    print(encode(report))

if __name__=='__main__':main()

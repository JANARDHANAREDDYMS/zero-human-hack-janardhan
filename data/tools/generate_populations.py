#!/usr/bin/env python3
"""Construct synthetic demo profiles from saved segment templates; no model/API calls.

python3 data/tools/generate_populations.py --product sony-speaker --pilot
python3 data/tools/generate_populations.py --product sony-speaker
python3 data/tools/generate_populations.py --all
python3 data/tools/generate_populations.py --all --check
"""
import argparse
import hashlib
import json
import math
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0'

def read(path):
    return json.loads(path.read_text())

def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def construct(folder):
    spec = read(folder / 'segments.json')
    rules = read(folder / 'sampling-rules.json')
    rng = random.Random(rules['seed'])
    allocation = {x['segment_id']: x['count'] for x in rules['segment_allocations']}
    profiles = []
    for s in spec['segments']:
        for local_index in range(allocation[s['segment_id']]):
            ctx = {k: rng.choice(v) for k, v in s['category_context'].items()}
            maximum = rng.randint(*s['budget_maximum_range'])
            comfortable = math.floor(maximum * rng.uniform(.60, .90))
            days = rng.choice(s['urgency_days_options'])
            requirements = []
            for r in s['requirements']:
                value = rng.choice(r['values'])
                if spec['product_id'] == 'proofreading' and r['attribute'] == 'word_limit':
                    value = ctx['document_words']
                requirements.append({'attribute': r['attribute'], 'operator': r['operator'],
                    'constraint': 'hard' if rng.random() < r['hard_probability'] else 'flexible',
                    'value': value, 'unit': r['unit']})
            if spec['product_id'] in {'resume-review', 'proofreading'}:
                requirements.append({'attribute': 'turnaround_hours', 'operator': 'lte',
                    'constraint': 'hard', 'value': days * 24, 'unit': 'hours'})
            selected = rng.sample(s['priority_pool'], 3)
            weights = [rng.randint(1, 9) for _ in selected]
            tradeoffs = [{'attribute': key, 'weight': round(w / sum(weights), 6)}
                for key, w in zip(selected, weights)]
            # Last weight closes rounding exactly; no outcome utility is computed.
            tradeoffs[-1]['weight'] = round(1 - sum(x['weight'] for x in tradeoffs[:-1]), 6)
            current = rng.choice(s['current_solutions'])
            retention = ['Time and effort to evaluate and set up an alternative']
            if any(x in current.lower() for x in ['working', 'existing', 'paid', 'subscription']):
                retention.append('An existing solution has value; replacing it must justify cost and effort')
            period = 'document_bundle' if spec['product_id'] == 'proofreading' else (
                'month' if spec['product_id'] in {'codesensei', 'resume-review'} else 'one_time')
            provenance = [
                {'field': 'segment_id', 'basis': 'assumption', 'source_ids': [s['segment_id']],
                    'note': 'Purchasing situation inspired by provider material; membership is invented.'},
                {'field': 'goal,purchase_trigger,current_solution,category_context', 'basis': 'assumption',
                    'source_ids': [s['segment_id']], 'note': 'Plausible template and sampled choices, not actual respondents.'},
                {'field': 'budget,urgency,requirements,tradeoffs,decision_style,switching_barriers,market',
                    'basis': 'assumption', 'source_ids': ['sampling-rules-v1'],
                    'note': 'Ranges, relationships, US market, and numerical values are explicit demo assumptions.'}]
            profile = {'customer_id': f"{spec['product_id']}-{len(profiles)+1:03d}",
                'segment_id': s['segment_id'], 'market': spec['market'], 'goal': s['goal'],
                'purchase_trigger': rng.choice(s['purchase_triggers']), 'current_solution': current,
                'budget': {'comfortable': comfortable, 'maximum': maximum, 'currency': 'USD',
                    'billing_period': period, 'scope_units': ctx.get('documents_needed', 1),
                    'upfront_maximum': maximum, 'scope_note': 'Total across documents_needed during this evaluation' if period == 'document_bundle' else 'One purchase or the first month of access; upfront commitment must also fit'},
                'urgency': {'deadline_days': days, 'basis': 'assumed relative time horizon'},
                'requirements': requirements, 'tradeoffs': tradeoffs,
                'decision_style': {'research_effort': rng.choice(['low', 'medium', 'high']),
                    'evidence_need': rng.choice(['basic', 'comparison', 'independent']),
                    'category_familiarity': rng.choice(['low', 'medium', 'high']),
                    'evaluation_action_budget': rng.choice([3, 4, 5])},
                'switching_barriers': retention, 'category_context': ctx,
                'provenance': provenance, 'synthetic': True}
            profiles.append(profile)
    return {'schema_version': '1.1', 'product_id': spec['product_id'], 'record_type': 'customers',
        'status': 'prepared_for_demo', 'population_version': rules['population_version'],
        'seed': rules['seed'], 'generator_version': VERSION,
        'input_hashes': {'segments_sha256': digest(spec), 'rules_sha256': digest(rules)},
        'count': len(profiles), 'customers': profiles,
        'limitations': ['Synthetic individuals, not real respondents or demand observations.',
            'Equal segment coverage is not market weighting; numerical distributions are assumptions.',
            'No customer choices, journey histories, or launch verdicts are assigned.']}

def validate(folder, population):
    spec = read(folder / 'segments.json')
    rules = read(folder / 'sampling-rules.json')
    expected = {s['segment_id']: s for s in spec['segments']}
    allocation = {x['segment_id']: x['count'] for x in rules['segment_allocations']}
    profiles = population['customers']
    assert population['count'] == len(profiles) == rules['target_count']
    assert Counter(p['segment_id'] for p in profiles) == allocation
    assert len({p['customer_id'] for p in profiles}) == len(profiles)
    assert len({digest({k:v for k,v in p.items() if k != 'customer_id'}) for p in profiles}) == len(profiles)
    evidence = read(folder / 'evidence.json')
    sources = {x['source_id'] for x in evidence['sources']}
    for s in spec['segments']:
        assert set(s['source_ids']) <= sources, (s['segment_id'], set(s['source_ids']) - sources)
    for p in profiles:
        s = expected[p['segment_id']]
        b = p['budget']
        assert 0 <= b['comfortable'] <= b['maximum'] == b['upfront_maximum']
        assert s['budget_maximum_range'][0] <= b['maximum'] <= s['budget_maximum_range'][1]
        assert p['urgency']['deadline_days'] in s['urgency_days_options']
        assert abs(sum(t['weight'] for t in p['tradeoffs'])-1) < 1e-5
        assert all(t['attribute'] in s['priority_pool'] and t['weight'] > 0 for t in p['tradeoffs'])
        assert 3 <= p['decision_style']['evaluation_action_budget'] <= 5
        assert not set(p) & {'choice', 'outcome', 'preferred_product', 'will_buy', 'conversion', 'launch_verdict'}
        assert p['synthetic'] and p['market'] == spec['market']
        provenance_sources = sources | set(expected) | {'sampling-rules-v1'}
        assert all(set(x['source_ids']) <= provenance_sources for x in p['provenance'])
        for k,v in p['category_context'].items():
            assert v in s['category_context'][k]
        for r in p['requirements']:
            if r['attribute'] == 'turnaround_hours':
                assert r['value'] == p['urgency']['deadline_days'] * 24
            else:
                template = next(t for t in s['requirements'] if t['attribute'] == r['attribute'])
                assert r['operator'] == template['operator']
                if population['product_id'] == 'proofreading' and r['attribute'] == 'word_limit':
                    assert r['value'] == p['category_context']['document_words']
                else:
                    assert r['value'] in template['values']
    # Deterministic generation must reproduce the same bytes, not just the same count.
    assert encode(construct(folder)) == encode(population)
    return {'product_id': population['product_id'], 'count': len(profiles),
        'segment_counts': dict(Counter(p['segment_id'] for p in profiles)),
        'unique_profiles': len(profiles), 'budget_maximum_range': [min(p['budget']['maximum'] for p in profiles), max(p['budget']['maximum'] for p in profiles)],
        'reproducibility': 'passed', 'consistency': 'passed', 'source_references': 'passed',
        'external_validity': 'not established', 'customer_choices': 'not generated'}

def review(folder, pop, report):
    lines = [f"# Population review: {pop['product_id']}", '',
        'Status: **Prepared for demo input; structural checks passed. Human and market validation pending.**', '',
        f"Population: {pop['count']} synthetic profiles; version {pop['population_version']}; seed {pop['seed']}.", '',
        '## Completed checks', '',
        '- Exact counts, unique IDs, and unique non-ID profiles.',
        '- Budgets, deadlines, allowed category values, normalized priorities, and conditional document lengths.',
        '- Segment evidence references and per-profile assumption provenance.',
        '- Byte-identical reproduction from saved rules and templates.',
        '- No preassigned choices, outcomes, or launch recommendation.', '',
        '## Segment coverage', '']
    lines += [f'- {k}: {v}' for k,v in report['segment_counts'].items()]
    lines += ['', '## Qualitative review', '',
        'The five templates cover different purchasing situations rather than mutually exclusive personality traits. Profiles vary in current solution, budget, urgency, requirements, priorities, and evidence needs. Needs are expressed independently of the client brand and advertised differentiator. Keeping a current solution, selecting a free alternative, and declining remain available.', '',
        'A five-profile pilot (one per segment) is preserved in data/simulation/pilots/. It checks readability and field fit before the full set. Automated checks validate the full population, not behavioral accuracy.', '',
        '## Assumptions and unresolved concerns', '',
        '- All numerical ranges and ten-per-segment allocations are designed assumptions; not empirical distributions.',
        '- Provider pages substantiate available offers and attributes, not prevalence of the proposed segments.',
        '- US/en/USD is a consistent demo assumption; intended markets need client confirmation.',
        '- Only 50 cases: report by segment and inspect sensitivity to population weighting.',
        '- No actual buyer, expert, or Terac review has been performed. No predictive accuracy claimed.',
        '- Selected product research is incomplete and prices/availability may change; preserve unknowns and source conflicts.',
        '- Hard constraints, value judgments, and price-period comparisons still need runtime enforcement.',
        '- Profiles with needs no available offer satisfies are permitted; do not repair them to favor the client.', '',
        'Next: implement the shared contract, inspect ten live journeys and their costs, then compare variants with the same profiles.']
    (folder/'population-review.md').write_text('\n'.join(lines)+'\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--product'); target.add_argument('--all', action='store_true')
    parser.add_argument('--pilot', action='store_true', help='Write one profile per segment; do not overwrite customers.json')
    parser.add_argument('--check', action='store_true', help='Validate saved full populations without rewriting')
    args = parser.parse_args()
    if args.pilot and args.check:
        parser.error('--pilot and --check cannot be combined')
    folders = sorted(p for p in (ROOT/'products').iterdir() if p.is_dir() and (p/'sampling-rules.json').exists()) if args.all else [ROOT/'products'/args.product]
    reports=[]
    for folder in folders:
        pop = read(folder/'customers.json') if args.check else construct(folder)
        report = validate(folder, pop)
        if args.pilot:
            seen=set(); pilot=[]
            for p in pop['customers']:
                if p['segment_id'] not in seen:
                    seen.add(p['segment_id']); pilot.append(p)
            out=ROOT/'simulation/pilots';out.mkdir(parents=True,exist_ok=True)
            (out/f'{folder.name}.json').write_text(encode({'status':'synthetic_pilot','product_id':folder.name,'count':len(pilot),'customers':pilot}))
        elif not args.check:
            (folder/'customers.json').write_text(encode(pop))
            review(folder,pop,report)
        reports.append(report)
    print(encode(reports))

if __name__ == '__main__':
    main()

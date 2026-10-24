"""Research planning and conservative evidence-coverage diagnostics.

These checks report missing support. They do not verify source meaning or turn
an anecdote into a representative customer distribution.
"""
import json

TRACKS=('offers','buyer_situations','counterevidence')

def research_plan(brief):
    # Start with category to avoid searching only for the client's standout.
    topic=(brief.get('category') or brief.get('name') or brief['description'])[:500]
    suffixes=(
        'competing alternatives official prices specifications limitations',
        'buyer reviews discussions purchase trigger current solution constraints tradeoffs',
        'satisfied existing users repair borrow free alternatives no need upgrade complaints')
    return [{'track':track,'query':f'{topic} {suffix}'} for track,suffix in zip(TRACKS,suffixes)]

def segmentation_quality(spec,evidence):
    findings={f['finding_id']:f for f in evidence['findings']}
    tracks={t:[] for t in TRACKS}
    for f in findings.values():
        if f.get('track') in tracks and f['basis'] not in {'assumption','unknown'}:
            tracks[f['track']].append(f['finding_id'])
    warnings=[f'No classified supporting findings for {t}; a search attempt is not evidence.' for t in TRACKS if not tracks[t]]
    segments=[];seen=set()
    for seg in spec['segments']:
        linked=[findings[fid] for fid in seg['rationale']['finding_ids']]
        buyer=[f['finding_id'] for f in linked if f['basis']=='observed_report' and f.get('track') in {'buyer_situations','counterevidence'}]
        notes=[]
        if not buyer:notes.append('No linked buyer report; segment is provisional even if competitor specifications are cited.')
        if len({sid for fid in buyer for sid in findings[fid]['source_ids']})==1:
            notes.append('Buyer support comes from one source; multiple findings do not establish independent corroboration.')
        if 'situation' not in seg:notes.append('Missing structured purchasing situation (legacy/offline input).')
        else:
            signature=tuple(seg['situation'][k].strip().casefold() for k in ['trigger','current_solution','constraint'])
            if signature in seen:notes.append('Duplicate trigger/current-solution/constraint; review segment distinctness.')
            seen.add(signature)
        fixed=[k for k,v in seg['fields'].items() if v['rule']['kind']=='constant']
        segments.append({'segment_id':seg['segment_id'],'status':'evidence_informed_hypothesis' if buyer and 'situation' in seg else 'provisional',
            'buyer_finding_ids':buyer,'buyer_source_count':len({sid for fid in buyer for sid in findings[fid]['source_ids']}),'warnings':notes,'constant_fields':fixed,
            'numeric_distributions':'assumed_unless_individually_supported'})
    return {'status':'diagnostic_not_market_validation','track_findings':tracks,'warnings':warnings,
        'segments':segments,'allocation_basis':spec['allocation_basis'],
        'evidence_limitations':list(evidence.get('limitations',[])),
        'limitations':['Counts measure scenario coverage, not market share.','Linked reports may be biased, duplicated, historical or unverified; semantic review is still required.','Constant fields are reported for review, not automatically errors.']}

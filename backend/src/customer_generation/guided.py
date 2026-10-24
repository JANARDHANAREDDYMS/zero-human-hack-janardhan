"""Durable human segmentation checkpoint and free local profile construction."""
import json
from pathlib import Path
from .sampling import generate_population,fingerprint
from .population_quality import population_quality,require_population_quality
from .state import utc_now
from customer_simulation.pipeline import read,save

def checkpoint_inputs(folder):
    folder=Path(folder);checkpoint=read(folder/'segmentation-checkpoint.json')
    spec=read(folder/'specification.json');evidence=read(folder/'evidence.json');brief=read(folder/'brief.json')
    for key,value in [('specification',spec),('evidence',evidence),('brief',brief)]:
        if fingerprint(value)!=checkpoint[key+'_sha256']:raise ValueError('Segmentation changed after review; a fresh review is required')
    return spec,evidence,brief,checkpoint

def finish_profiles(folder):
    folder=Path(folder);spec,evidence,brief,checkpoint=checkpoint_inputs(folder)
    approval=read(folder/'segmentation-approval.json')
    if approval['checkpoint_sha256']!=fingerprint(checkpoint):raise ValueError('Segmentation approval does not match the reviewed inputs')
    state=read(folder/'state.json');state.update(status='running',stage='profile_generation',error=None);save(folder/'state.json',state)
    counts={s['segment_id']:0 for s in spec['segments']}
    # Local construction is restartable; no provider calls happen here.
    cards=folder/'profile-cards.jsonl';cards.write_text('')
    def progress(customer,completed,total):
        counts[customer['segment_id']]+=1
        card={k:customer[k] for k in ['customer_id','segment_id','goal','current_solution','purchase_trigger','budget']}
        with cards.open('a') as stream:stream.write(json.dumps(card)+'\n')
        save(folder/'profile-progress.json',{'completed':completed,'planned':total,'segments':counts})
    population=generate_population(spec,evidence,stratified=True,on_customer=progress)
    quality=population_quality(spec,population,brief);require_population_quality(quality)
    save(folder/'population-quality.json',quality);save(folder/'customers.json',population)
    save(folder/'validation.json',{'status':'passed','count':population['count'],
        'specification_sha256':population['specification_sha256'],'evidence_sha256':population['evidence_sha256'],
        'review_mode':'model_review_and_human_segmentation_approval','behavioral_validity':'not_evaluated'})
    state.update(status='completed',stage='completed',finished_at=utc_now())
    state['events'].append({'at':utc_now(),'stage':'profile_generation','status':'passed'})
    save(folder/'state.json',state)
    return population

def live_details(folder,simulation):
    folder=Path(folder);simulation=Path(simulation)
    def optional(name):
        p=folder/name
        return read(p) if p.exists() else None
    result={'research_progress':optional('research-progress.json'),'profile_progress':optional('profile-progress.json')}
    spec=optional('specification.json')
    result['segments']=[]
    if spec:
        for segment in spec['segments']:
            situation=segment.get('situation',{})
            result['segments'].append({'segment_id':segment['segment_id'],'name':segment['name'],'count':segment['count'],
                'goal':segment['goal'],'current_solution':situation.get('current_solution'),
                'trigger':situation.get('trigger'),'constraint':situation.get('constraint'),
                'switch_reason':situation.get('switch_reason'),'stay_reason':situation.get('stay_reason')})
    cards=folder/'profile-cards.jsonl';result['profile_cards']=[]
    if cards.exists():
        for line in cards.read_text().splitlines():
            try:result['profile_cards'].append(json.loads(line))
            except json.JSONDecodeError:continue # An append can overlap a read.
    elif (folder/'customers.json').exists():
        result['profile_cards']=[{k:c[k] for k in ['customer_id','segment_id','goal','current_solution','purchase_trigger','budget']} for c in read(folder/'customers.json')['customers']]
    result['simulation_customers']=[]
    for p in sorted(simulation.glob('customer-*.json')):
        if not p.stem.removeprefix('customer-').isdigit():continue
        value=read(p)
        result['simulation_customers'].append({k:value.get(k) for k in ['customer_id','decision','headline','customer_story']})
    return result

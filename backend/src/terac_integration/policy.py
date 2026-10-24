import json
from pathlib import Path
POLICY_PATH=Path(__file__).resolve().parents[3]/'data/terac/expert-policy.json'

def expert_policy():
    policy=json.loads(POLICY_PATH.read_text())
    if (type(policy['experts_per_improvement']) is not int or policy['experts_per_improvement']!=1 or policy['country_of_residence']!='US' or
        policy['work_location']!='US' or policy['language']!='English' or policy['allow_outside_us'] is not False or
        policy['automatic_launch'] is not False or policy['scope']!='all_products'):
        raise ValueError('Expert sourcing must remain one English-speaking US-based expert per improvement, with no automatic launch')
    return policy

def validate_expert_brief(improvement):
    brief=improvement.get('expert_brief')
    if not isinstance(brief,dict):raise ValueError('A product-specific expert brief is required before sourcing; a generic role, country and language are insufficient')
    for field in ['role','product_domain','deliverable']:
        if not isinstance(brief.get(field),str) or not brief[field].strip():raise ValueError('Expert brief needs '+field)
    for field in ['relevant_experience','qualification_checks']:
        values=brief.get(field)
        if not isinstance(values,list) or len(values)<2 or any(not isinstance(v,str) or not v.strip() for v in values):
            raise ValueError('Expert brief needs at least two concrete '+field+' entries')
    if brief.get('work_type') not in {'review','implementation_plan','implementation'}:raise ValueError('Expert work must distinguish review, implementation planning and implementation')
    if brief['work_type']=='implementation' and not brief.get('required_access_confirmed'):
        raise ValueError('Implementation cannot be scoped without confirmed access and a reviewable change request')
    return brief

def feasibility_arguments(product,improvement):
    expert_policy();brief=validate_expert_brief(improvement)
    explanation=improvement['explanation']
    question=improvement.get('review_question') or improvement.get('proposed_next_step') or improvement.get('proposed_test')
    if not all(isinstance(v,str) and v.strip() for v in [explanation,question]):raise ValueError('Improvement needs explanation and a review question')
    name=product.get('name') if isinstance(product,dict) else product
    background=' '.join(brief['relevant_experience'])
    checks=' '.join(brief['qualification_checks'])
    work={'review':'Expert review and recommendation only.',
        'implementation_plan':'Implementation planning only; no code access or authority to change a live product is granted.',
        'implementation':'Implementation limited to the supplied, authorized change request.'}[brief['work_type']]
    return {'submissionCount':1,
        'panelDescription':'Exactly one English-speaking expert who CURRENTLY RESIDES IN the United States and will perform this work while PHYSICALLY BASED IN the United States. Exclude everyone based outside the US, regardless of citizenship. Required role: '+brief['role']+'. Product domain: '+brief['product_domain']+'. Required hands-on experience: '+background+' Qualification checks: '+checks+' English fluency and a broad job-function label alone do not qualify someone.',
        'taskDescription':'For '+str(name)+', investigate this concern from synthetic customer feedback (not a verified defect): '+explanation+' Review question / proposed investigation: '+question+' '+work+' Required deliverable: '+brief['deliverable']+' State assumptions, unavailable evidence and prerequisites. Do not claim to have tested, implemented or improved sales without evidence. This is a sourcing-feasibility request only, not permission to recruit or hire.'}

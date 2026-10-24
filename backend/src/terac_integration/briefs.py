"""Prepare sourcing requirements from saved concerns, never candidate credentials.

Template construction is deterministic and makes no model or Terac calls.
The role is already proposed by the concern-extraction model.
"""
import re
from .policy import validate_expert_brief

def prepare_expert_brief(product,concern):
    role=concern['suggested_expertise'].strip()
    # Category experience transfers between products; a private product name is
    # never a prerequisite for someone to qualify.
    domain=str(product.get('category') or '').strip()
    name=str(product.get('name') or '').strip()
    if name:
        domain=re.sub(re.escape(name),'',domain,flags=re.I).strip(' /-:')
        brand=name.split()[0]
        if len(brand)>3:domain=re.sub(r'\b'+re.escape(brand)+r'\b','',domain,flags=re.I).strip(' /-:')
    domain=domain or role
    question=concern['review_question'].strip()
    title=concern['title'].strip()
    brief={
        'role':role,'product_domain':domain,'work_type':'review',
        'relevant_experience':[
            f'Personally delivered {role.lower()} work for {domain.lower()} or a closely related offering.',
            f'Investigated a comparable customer problem: {title}. Can explain their own contribution, the tradeoffs and the outcome.'
        ],
        'qualification_checks':[
            f'Describe a relevant {domain.lower()} project in which you performed {role.lower()} work. What did you personally do?',
            f'How would you investigate this question: {question} What evidence, constraints and tradeoffs would you check before recommending a change?'
        ],
        'deliverable':f'A short written assessment answering: {question} Evaluate this proposed test: {concern["proposed_test"]} Include a practical recommendation, assumptions, risks and evidence still needed. No product access or implementation is included.',
        'scope_basis':'Automatically prepared sourcing requirements from the saved product category and synthetic concern; not verified candidate qualifications.'
    }
    validate_expert_brief({'expert_brief':brief})
    return brief

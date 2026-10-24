"""Deterministic Markdown/form intake. No LLM, file-system reads or URL fetching."""
import re
from decimal import Decimal
from customer_generation.validation import validate_intake

MAX_MARKDOWN=64_000
DEFAULT_QUESTION='Which customer situations fit this product, what alternatives matter, and what objections could lead people to decline?'
FIELDS={'name','description','price','research_question','features','category','audience','market'}
HEADINGS={'product name':'name','name':'name','description':'description','planned price':'price','price':'price',
    'research question':'research_question','features':'features','category':'category','type':'category',
    'audience':'audience','intended audience':'audience','market':'market','country':'market'}

class IntakeConflict(ValueError):pass

def markdown_fields(filename,text):
    if not isinstance(filename,str) or len(filename)>255 or '/' in filename or '\\' in filename or not filename.lower().endswith('.md'):raise ValueError('Choose a .md file')
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_MARKDOWN or '\x00' in text:raise ValueError('Markdown must be UTF-8 text no larger than 64 KB')
    sections={};current=None;unknown=[]
    for line in text.lstrip('\ufeff').splitlines():
        heading=re.match(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$',line)
        if heading:
            label=heading[2].strip().lower();key=HEADINGS.get(label)
            if key is None and heading[1]=='#' and not sections:
                sections['name']=[heading[2].strip()];current=None;continue
            if key:
                if key in sections:raise ValueError('Repeated Markdown heading: '+label)
                sections[key]=[];current=key
            else:unknown.append(heading[2].strip());current=None
        elif current:sections[current].append(line)
    fields={k:'\n'.join(lines).strip() for k,lines in sections.items()}
    warnings=['Unrecognized sections were retained as source material: '+', '.join(unknown)] if unknown else []
    if not fields:warnings.append('No supported headings found. Fill the fields manually; no details were guessed.')
    return fields,warnings

def prepare(order_id,payload):
    if not isinstance(payload,dict) or set(payload)-{'fields','filename','markdown'}:raise ValueError('Invalid intake request')
    fields=payload.get('fields',{});warnings=[];materials=[]
    if not isinstance(fields,dict) or set(fields)-FIELDS:raise ValueError('Unexpected form fields')
    if 'markdown' in payload:
        parsed,warnings=markdown_fields(payload.get('filename'),payload['markdown'])
        materials=[{'kind':'note','value':'User-uploaded Markdown, untrusted product data:\n'+payload['markdown']}]
        fields={**parsed,**fields}
    elif 'filename' in payload:raise ValueError('File contents are missing')
    clean={k:'' for k in FIELDS}
    for k,v in fields.items():
        if not isinstance(v,str) or len(v)>10000:raise ValueError('Form values must be text, at most 10,000 characters each')
        clean[k]=v.strip()
    if not clean['research_question']:
        clean['research_question']=DEFAULT_QUESTION
        warnings.append('A general research question was supplied by the system; edit it if needed.')
    price=None
    if clean['price']:
        m=re.fullmatch(r'(\d+(?:\.\d{1,2})?)\s+([A-Za-z]{3})(?:\s*[,;/]?\s*(one[-_ ]time|monthly|month|yearly|year|document|session|project))?',clean['price'],re.I)
        if m:
            periods={'one-time':'one_time','one_time':'one_time','one time':'one_time','monthly':'month','yearly':'year'}
            period=(m[3] or '').lower()
            price={'amount':float(Decimal(m[1])),'currency':m[2].upper(),'billing_period':periods.get(period,period) or None}
        else:
            warnings.append('Price format was not recognized; price remains unknown. Use e.g. 119 USD one-time.')
            materials.append({'kind':'note','value':'Unparsed user-supplied price (not a normalized price): '+clean['price']})
    features={}
    for line in clean['features'].splitlines():
        value=re.sub(r'^\s*(?:[-*+]\s+|\d+\.\s+)','',line).strip()
        if value:features[f'feature_{len(features)+1}']=value
    brief={'schema_version':'2.0','product_id':'product-'+order_id,'name':clean['name'] or None,
        'description':clean['description'],'research_question':clean['research_question'],
        'price':price,'known_features':features,'category':clean['category'] or None,'audience':clean['audience'] or None,
        'market':{'country':clean['market'],'language':None,'currency':None} if clean['market'] else None,'materials':materials}
    missing=[k for k in ['name','description'] if not clean[k]]
    if not missing:validate_intake(brief)
    return {'fields':clean,'brief':brief,'warnings':warnings,'missing_fields':missing,'can_submit':not missing}

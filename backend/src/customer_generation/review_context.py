"""Lossless deduplication of repeated long strings in review inputs."""
import copy
from collections import Counter


def compact_review_context(payload):
    counts=Counter()
    def count(v):
        if isinstance(v,str) and len(v)>=100:counts[v]+=1
        elif isinstance(v,dict):
            for x in v.values():count(x)
        elif isinstance(v,list):
            for x in v:count(x)
    count(payload)
    ids={s:f't{i+1}' for i,(s,n) in enumerate(counts.items()) if n>1}
    def encode(v):
        if isinstance(v,str) and v in ids:return {'$review_text':ids[v]}
        if isinstance(v,dict):return {k:encode(x) for k,x in v.items()}
        if isinstance(v,list):return [encode(x) for x in v]
        return copy.deepcopy(v)
    return {'review_representation':'Lossless shared-text representation. Every object containing only $review_text stands for the exact string at that key in shared_text. Resolve these references when reading review_payload. All evidence, rules, provenance, pilot values and IDs are retained.',
        'shared_text':{i:s for s,i in ids.items()},'review_payload':encode(payload)}


def expand_review_context(context):
    def decode(v):
        if isinstance(v,dict):
            if set(v)=={'$review_text'}:return context['shared_text'][v['$review_text']]
            return {k:decode(x) for k,x in v.items()}
        if isinstance(v,list):return [decode(x) for x in v]
        return v
    return decode(context['review_payload'])

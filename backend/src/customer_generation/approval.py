"""Summary-only human approval, bound to exact saved simulation inputs."""
import hashlib,html,json
from collections import Counter
from pathlib import Path

def read_population(run):
    run=Path(run)
    state=json.loads((run/'state.json').read_text())
    if state['status']!='completed':raise ValueError('Only completed populations can be approved')
    spec=json.loads((run/'specification.json').read_text());customers=json.loads((run/'customers.json').read_text())
    counts=Counter(c['segment_id'] for c in customers['customers'])
    if counts!=Counter({s['segment_id']:s['count'] for s in spec['segments']}):raise ValueError('Population counts do not match specification')
    hashes={n:hashlib.sha256((run/n).read_bytes()).hexdigest() for n in ['customers.json','specification.json','evidence.json']}
    return spec,counts,hashes

def summary_lines(run):
    spec,counts,_=read_population(run)
    segments=spec['segments'];rows=[f"{s['name']} — {counts[s['segment_id']]} customers." for s in segments]
    # Always five lines, while retaining every segment and its count.
    groups=[rows[i*len(rows)//4:(i+1)*len(rows)//4] for i in range(4)]
    quality_path=Path(run)/'population-quality.json'
    coverage=''
    if quality_path.exists():
        quality=json.loads(quality_path.read_text());n=quality['comparable_customers'];a=quality['can_afford']
        if n:coverage=f' {a} can afford the stated price; {n-a} cannot. Budget ranges are scenario assumptions unless supported by evidence.'
    return [f"{spec['target_count']} synthetic customers across {len(segments)} segments. Counts are demo coverage, not market shares."+coverage]+[' '.join(g) if g else 'No additional segment.' for g in groups]

def write_summary(run):
    run=Path(run);lines=summary_lines(run)
    (run/'population-summary.md').write_text('\n'.join(lines)+'\n')
    (run/'population-summary.html').write_text('<!doctype html><meta charset="utf-8"><title>Population summary</title><main style="max-width:800px;margin:60px auto;font:18px/1.6 system-ui">'+''.join('<p>'+html.escape(x)+'</p>' for x in lines)+'<p>To approve these inputs for simulation, open the local approval page with:<br><code>python3 backend/scripts/review_population.py --run-id '+html.escape(run.name)+'</code></p></main>')
    return run/'population-summary.md'

def approval_valid(run,approval_path):
    _,_,hashes=read_population(run)
    try:data=json.loads(Path(approval_path).read_text())
    except (OSError,ValueError):return False
    return data.get('run_id')==Path(run).name and data.get('input_hashes')==hashes and data.get('scope')=='summary_approval_for_simulation'

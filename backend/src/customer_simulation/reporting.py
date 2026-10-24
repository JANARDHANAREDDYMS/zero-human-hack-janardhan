"""Readable, local-only report UI. No model calls or expert submissions."""
import html,json,re
from collections import Counter

def esc(value):return html.escape(str(value))
def plain(value):
    replacements={'purchasable offer':'product available to buy','purchasable option':'product available to buy',
        'meaningful audio improvement':'sound better than the existing setup','decision-ready':'clear enough to decide',
        'billing scope':'what the price includes','billing terms':'payment terms','the target concept':'the proposed product',
        'The target concept':'The proposed product','the target’s':'the proposed product’s','The target’s':'The proposed product’s',
        "the target's":"the proposed product's","The target's":"The proposed product's",'the target':'the proposed product','The target':'The proposed product'}
    for old,new in replacements.items():value=value.replace(old,new)
    return value

def render_report(out,results,customers,offers,summary,briefs):
    by_id={c['customer_id']:c for c in customers};index={r['customer_id']:n for n,r in enumerate(results,1)}
    names={};language={}
    language_path=out/'report-language.json'
    if language_path.exists() and (out/'inputs.json').exists():
        from .pipeline import fingerprint
        candidate=json.loads(language_path.read_text())
        if candidate.get('input_sha256')==fingerprint(json.loads((out/'inputs.json').read_text())):
            language=candidate
    stories=language.get('customers',{});group_stories=language.get('segments',{})
    manifest=out/'manifest.json'
    if manifest.exists():
        from pathlib import Path
        m=json.loads(manifest.read_text());p=Path(m.get('source_run',''))/'specification.json'
        if p.is_file():names={s['segment_id']:s['name'] for s in json.loads(p.read_text())['segments']}
    counts=summary['decisions'];issues=summary['issues']
    top=sorted(issues,key=lambda k:-len({i['customer_id'] for i in issues[k]}))
    overview=[f"Tested {len(results)} synthetic customers across {len(summary['segments'])} customer groups.",
        f"{counts.get('choose_product',0)} chose the proposed product; {counts.get('choose_alternative',0)} chose a competitor.",
        f"{counts.get('keep_current',0)} kept their current solution; {counts.get('defer',0)} decided to wait.",
        'Most frequently raised concerns: '+(', '.join(k.replace('_',' ') for k in top[:3]) or 'none recorded')+'.',
        'Next: review the customer reasons below and test one specific change before drawing a launch conclusion.',
        'These are simulated choices. No human interviews, physical product tests, or real purchases occurred.']
    overview=language.get('overview',overview)
    names.update({sid:group['name'] for sid,group in group_stories.items()})
    labels={'choose_product':'Choose proposed product','choose_alternative':'Choose competitor','keep_current':'Keep current solution','defer':'Wait before deciding'}
    body=['''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Customer feedback report</title><style>
body{margin:0;background:#f5f6fa;color:#182338;font:16px/1.6 system-ui}main{max-width:1280px;margin:auto;padding:36px 24px}h1{font-size:36px;line-height:1.2}h2{margin-top:0}section,aside{background:white;border:1px solid #dce2eb;border-radius:16px;padding:24px;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:15px}th,td{text-align:left;padding:14px;border-bottom:1px solid #e1e6ef;vertical-align:top}th{background:#f0f3f9}small,.muted{color:#526079}.layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:24px}.scroll{overflow-x:auto}aside{align-self:start;position:sticky;top:20px}button{background:#2455dc;color:white;border:0;border-radius:10px;padding:16px 20px;font:600 17px system-ui;cursor:pointer;width:100%}button.secondary{background:#e9edf7;color:#182338;margin-top:12px}details{border-top:1px solid #e1e6ef;padding:14px 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}dialog{max-width:760px;width:85vw;border:1px solid #ccd4e2;border-radius:16px;padding:28px}label{display:block;font-weight:600;margin-top:16px}select,textarea{width:100%;box-sizing:border-box;padding:10px;font:inherit}textarea{min-height:130px}@media(max-width:900px){.layout{display:block}aside{position:static}main{padding:16px}h1{font-size:28px}}
</style></head><body><main><small>RESEARCH → CUSTOMER CHOICES → FEEDBACK → IMPROVEMENTS</small><h1>What customers chose — and why</h1><p>'''+esc(offers[0]['name'])+'''</p><div class="layout"><div><section><h2>Overall feedback</h2>''']
    body.extend('<p>'+esc(x)+'</p>' for x in overview)
    body.append('<small>These are simulated customers, not people we interviewed. Rewritten explanations are editorial summaries; original responses remain available below.</small>')
    body.append('</section><section><h2>Each customer’s decision</h2><p class="muted">Plain-language display of saved synthetic responses. Full evidence and original wording remain below.</p><div class="scroll"><table><thead><tr><th>Customer</th><th>Situation</th><th>Choice</th><th>Reason</th></tr></thead><tbody>')
    for r in results:
        c=by_id[r['customer_id']];n=index[r['customer_id']];budget=c['budget']
        situation=stories.get(r['customer_id'],{}).get('situation',c['current_solution']+'. '+c['goal'])
        reasons=stories.get(r['customer_id'],{}).get('reason',' '.join(plain(x['explanation']) for x in r['reasons'][:2]))
        body.append(f'<tr><td><a href="#customer-{n}">Customer {n}</a><br><small>{esc(names.get(c["segment_id"],c["segment_id"]))}</small></td><td>{esc(situation)}<br><strong>Budget: {esc(budget["currency"])} {budget["maximum"]:.0f}</strong></td><td>{esc(labels[r["decision"]])}</td><td>{esc(reasons)}</td></tr>')
    body.append('</tbody></table></div></section><section><h2>Feedback by customer group</h2>')
    for sid,segment in summary['segments'].items():
        tested=[r for r in results if by_id[r['customer_id']]['segment_id']==sid]
        label=names.get(sid,by_id[tested[0]['customer_id']]['goal'])
        body.append('<h3>'+esc(label)+' — '+str(segment['count'])+' tested</h3>')
        body.append('<p>'+esc('; '.join(f'{v} {labels[k].lower()}' for k,v in segment['decisions'].items()))+'.</p>')
        if sid in group_stories:body.append('<p>'+esc(group_stories[sid]['feedback'])+'</p>')
        for r in tested:
            n=index[r['customer_id']]
            body.append('<p><a href="#customer-'+str(n)+'">Customer '+str(n)+'</a>: '+esc(stories.get(r['customer_id'],{}).get('reason',plain(r['headline'])))+'<br><strong>What might help:</strong> '+esc(stories.get(r['customer_id'],{}).get('next_step',plain(r['change_that_might_help'])))+'</p>')
        body.append('<small>This group summary covers only the customers tested, not the whole market.</small>')
    body.append('</section><section><h2>Detailed customer feedback</h2>')
    for r in results:
        n=index[r['customer_id']]
        body.append(f'<details id="customer-{n}"><summary>Customer {n} · {esc(labels[r["decision"]])}</summary>')
        story=stories.get(r['customer_id'])
        if story:
            body.append('<p><strong>What is happening:</strong> '+esc(story['situation'])+'</p>')
            body.append('<p><strong>Why they made this choice:</strong> '+esc(story['reason'])+'</p>')
            body.append('<p><strong>What you could do next:</strong> '+esc(story['next_step'])+'</p>')
        else:
            body.append('<p><strong>Why:</strong> '+esc(plain(r['headline']))+'</p>')
            for reason in r['reasons']:body.append('<p>'+esc(plain(reason['explanation']))+'</p>')
            for issue in r['objections']:body.append('<p><strong>Concern:</strong> '+esc(plain(issue['concern']))+'<br><strong>Suggested improvement:</strong> '+esc(plain(issue['suggested_change']))+'</p>')
            body.append('<p><strong>What might change their mind:</strong> '+esc(plain(r['change_that_might_help']))+'</p>')
            body.append('<p><strong>Still unknown:</strong> '+esc(' '.join(r['missing_information']) or 'No additional information requested.')+'</p>')
        body.append('<details><summary>Original response and evidence references</summary><pre>'+esc(json.dumps(r,indent=2,ensure_ascii=False))+'</pre></details></details>')
    body.append('</section></div><aside><h2>Improvements to investigate</h2><p>Suggested changes from these simulated customers. These are proposals, not validated fixes.</p>')
    if language.get('improvements'):
        for change in language['improvements']:
            body.append('<h3>'+esc(change['title'])+'</h3><p>'+esc(change['text'])+'</p><small>Based on customers '+esc(', '.join(map(str,change['customer_numbers'])))+'</small>')
    elif top:
        for category in top:
            entries=issues[category];affected=sorted({index[i['customer_id']] for i in entries})
            body.append('<h3>'+esc(category.replace('_',' ').capitalize())+'</h3><p>'+str(len(affected))+' of '+str(len(results))+' customers raised this.</p>')
            changes=list(dict.fromkeys(plain(i['suggested_change']) for i in entries))
            for change in changes:body.append('<p>'+esc(change)+'</p>')
            body.append('<small>Supporting customers: '+esc(', '.join(map(str,affected)))+'</small>')
    else:body.append('<p>No improvement requests were recorded.</p>')
    body.append('<p class="muted">Priorities are ordered by the number of tested customers raising each topic. This is not a market demand ranking.</p></aside></div></main></body></html>')
    (out/'report.html').write_text(''.join(body))
    # Plain-language Markdown mirrors the visible report without extra model calls.
    lines=['# Customer feedback report',*overview,'','## Individual customers']
    for r in results:
        n=index[r['customer_id']];c=by_id[r['customer_id']]
        lines.extend(['',f'### Customer {n} — {labels[r["decision"]]}','Situation: '+stories.get(r['customer_id'],{}).get('situation',c['current_solution']+'. '+c['goal']),
            'Reason: '+stories.get(r['customer_id'],{}).get('reason',' '.join(plain(x['explanation']) for x in r['reasons'])), 'What might help: '+stories.get(r['customer_id'],{}).get('next_step',plain(r['change_that_might_help']))])
    lines.extend(['','## Segment feedback'])
    for sid,segment in summary['segments'].items():
        lines.append(names.get(sid,sid)+' — '+str(segment['count'])+' tested')
        if sid in group_stories:lines.append(group_stories[sid]['feedback'])
        lines.extend('- Customer '+str(index[f['customer_id']])+': '+stories.get(f['customer_id'],{}).get('reason',plain(f['headline'])) for f in segment['feedback'])
    lines.extend(['','## Improvements to investigate'])
    for category in top:
        lines.append(category.replace('_',' ').capitalize()+': '+str(len({i['customer_id'] for i in issues[category]}))+' customers')
        lines.extend('- '+plain(change) for change in dict.fromkeys(i['suggested_change'] for i in issues[category]))
    (out/'report.md').write_text('\n'.join(lines)+'\n')

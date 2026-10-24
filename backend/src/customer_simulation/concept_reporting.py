"""Render validated, model-written summaries; counts and layout belong to code."""
import html,json

def esc(value):return html.escape(str(value))
LABELS={'choose_product':'Would choose your product','choose_alternative':'Would choose an alternative','keep_current':'Would keep what they use','defer':'Would wait before choosing'}

def render_report(out,inputs,results,summary,narrative,*,coverage=None):
    customers={c['customer_id']:c for c in inputs['customers']};number={r['customer_id']:i for i,r in enumerate(results,1)}
    def refs(ids):return ', '.join('<a href="#customer-'+str(number[cid])+'">Customer '+str(number[cid])+'</a>' for cid in ids)
    counts=summary['decisions'];total=summary['evaluated']
    line=f"Of {total} simulated customers: {counts.get('choose_product',0)} would choose your product, {counts.get('choose_alternative',0)} an alternative, {counts.get('keep_current',0)} would keep what they use, and {counts.get('defer',0)} would wait."
    body=['''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customer feedback report</title><style>
body{margin:0;background:#f4f6fa;color:#1d2b40;font:16px/1.65 system-ui}main{max-width:1350px;margin:auto;padding:32px 24px}h1{font-size:36px;line-height:1.2}h2{margin-top:0}section,aside{background:white;border:1px solid #dce3ee;border-radius:16px;padding:24px;margin:20px 0}.layout{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:24px}aside{align-self:start}.note,small{color:#53637c}a{color:#2454bd}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:15px}td,th{padding:14px;text-align:left;vertical-align:top;border-bottom:1px solid #dde4ee}th{background:#f0f4fa}details{padding:16px 0;border-top:1px solid #dde4ee}summary{font-weight:600;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.assumption{border-left:4px solid #365dc8;padding:14px 18px;background:#ecf1ff}@media(max-width:950px){.layout{display:block}main{padding:16px}h1{font-size:28px}}
</style></head><body><main><small>PRODUCT IDEA → CUSTOMER CHOICES → FEEDBACK → IMPROVEMENTS</small><h1>What customers would choose — and why</h1><p>'''+esc(inputs['brief']['name'])+'''</p><p class="assumption"><strong>What we asked:</strong> If your proposed product were available at the stated price and worked as described, would this customer want it? Questions about proof, warranty and launch dates are listed separately below. This assumption is not verification of your claims.</p><p class="note">These are simulated customers, not people we interviewed. Choices are hypothetical interest, not orders or measured demand. This test compares offer descriptions; it does not test a website or physical product.</p><div class="layout"><div><section><h2>Overall feedback</h2><p>'''+esc(line)+'</p>']
    if coverage and coverage['mode']!='direct':
        body.append('<p class="note">All '+str(total)+' customer results were included through bounded batch summaries. Linked customer IDs are supporting examples, not the only people included. Exact counts below use every result.</p>')
    for point in narrative['overview']:body.append('<p>'+esc(point['text'])+'<br><small>Based on '+refs(point['customer_ids'])+'</small></p>')
    body.append('</section><section><h2>Each customer’s decision</h2><div class="scroll"><table><caption>What each person already uses, their choice and the reason behind it</caption><thead><tr><th>Customer</th><th>What is happening now</th><th>Choice</th><th>Why</th></tr></thead><tbody>')
    lines=['# What customers would choose — and why',inputs['brief']['name'],'',
        'Scenario: assume the proposed product is available at its stated price and works as described. This is not proof that it does.',
        'Synthetic feedback; no real interviews, purchases, website or physical testing.','',line]
    lines.extend(point['text']+' [Customers: '+', '.join(str(number[c]) for c in point['customer_ids'])+']' for point in narrative['overview'])
    lines.extend(['','## Individual customers'])
    for r in results:
        c=customers[r['customer_id']];n=number[r['customer_id']];story=r['customer_story'];budget=c['budget']
        body.append(f'<tr><td><a href="#customer-{n}">Customer {n}</a><br><small>Budget: {esc(budget["currency"])} {budget["maximum"]:.0f}</small></td><td>{esc(story["situation"])}</td><td>{esc(LABELS[r["decision"]])}</td><td>{esc(story["reason"])}</td></tr>')
        lines.extend(['',f'### Customer {n} — {LABELS[r["decision"]]}','Situation: '+story['situation'],'Reason: '+story['reason'],'What you could try: '+story['next_step']])
    body.append('</tbody></table></div></section><section><h2>Feedback by customer group</h2>');lines.extend(['','## Feedback by customer group'])
    for group in narrative['segments']:
        actual=summary['segments'][group['segment_id']]
        choices='; '.join(str(v)+' '+LABELS[k].lower() for k,v in actual['decisions'].items())
        body.append('<h3>'+esc(group['name'])+' — '+str(actual['count'])+' tested</h3><p>'+esc(choices)+'.</p><p>'+esc(group['feedback'])+'</p><p><strong>What you could try:</strong> '+esc(group['next_step'])+'</p><small>Based on '+refs(group['customer_ids'])+'. This describes the tested examples, not everyone in this market.</small>')
        lines.extend(['','### '+group['name']+' — '+str(actual['count'])+' tested',choices,group['feedback'],'What you could try: '+group['next_step']])
    body.append('</section><section><h2>More about each customer</h2>')
    for r in results:
        n=number[r['customer_id']];story=r['customer_story']
        body.append(f'<details id="customer-{n}"><summary>Customer {n} — {esc(LABELS[r["decision"]])}</summary><p><strong>Their situation:</strong> {esc(story["situation"])}</p><p><strong>Why:</strong> {esc(story["reason"])}</p><p><strong>What you could try:</strong> {esc(story["next_step"])}</p>')
        for objection in r['objections']:body.append('<p><strong>Concern about the product:</strong> '+esc(objection['concern'])+'<br><strong>Suggested change:</strong> '+esc(objection['suggested_change'])+'</p>')
        body.append('<details><summary>Original result and supporting profile/evidence references</summary><pre>'+esc(json.dumps(r,indent=2,ensure_ascii=False))+'</pre></details></details>')
    body.append('</section><section><h2>What they would check before paying</h2><p>These checks are separate from whether customers like your idea. A person can want the product and still ask for proof before buying it.</p>')
    lines.extend(['','## Checks before paying — separate from product appeal'])
    for r in results:
        n=number[r['customer_id']]
        if r['purchase_checks']:
            body.append('<h3>Customer '+str(n)+'</h3>')
            for check in r['purchase_checks']:
                body.append('<p>'+esc(check['question'])+'</p>');lines.append('Customer '+str(n)+': '+check['question'])
    if not any(r['purchase_checks'] for r in results):body.append('<p>No additional checks were requested in this sample.</p>')
    if summary['research_gaps']:
        body.append('<h3>Gaps in our competitor research</h3><p>These are limits of this comparison, not missing information you were required to supply.</p>')
        for gap in summary['research_gaps']:body.append('<p><strong>'+esc(gap['name'])+':</strong> '+esc(gap['gap'])+'</p>')
    body.append('</section></div><aside><h2>Improvements to try</h2><p>Suggestions drawn from these customers. They have not been tested yet.</p>');lines.extend(['','## Improvements to try'])
    for improvement in narrative['improvements']:
        body.append('<h3>'+esc(improvement['title'])+'</h3><p>'+esc(improvement['explanation'])+'</p><p><strong>Try this:</strong> '+esc(improvement['next_step'])+'</p><small>Based on '+refs(improvement['customer_ids'])+'</small>')
        lines.extend(['','### '+improvement['title'],improvement['explanation'],'Try this: '+improvement['next_step'], 'Supporting customers: '+', '.join(str(number[c]) for c in improvement['customer_ids'])])
    if not narrative['improvements']:body.append('<p>No product changes were proposed for this sample.</p>')
    body.append('</aside></div></main></body></html>')
    (out/'report.html').write_text(''.join(body));(out/'report.md').write_text('\n'.join(lines)+'\n')

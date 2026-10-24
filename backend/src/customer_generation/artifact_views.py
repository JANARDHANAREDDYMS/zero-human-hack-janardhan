"""Read-only, escaped HTML views of the fixed journey artifact allowlist."""
import html
import json
from urllib.parse import urlsplit

def render_artifact(path,name):
    text=path.read_text()
    if path.suffix=='.html':return text
    def esc(value):return html.escape(str(value),quote=True)
    def value(item):
        if isinstance(item,dict):
            return '<dl>'+''.join('<dt>'+esc(k.replace('_',' '))+'</dt><dd>'+value(v)+'</dd>' for k,v in item.items())+'</dl>'
        if isinstance(item,list):
            return '<ol>'+''.join('<li>'+value(v)+'</li>' for v in item)+'</ol>' if item else '<span>None recorded</span>'
        if isinstance(item,str) and urlsplit(item).scheme in {'https','http'}:
            return '<a target="_blank" rel="noopener noreferrer" href="'+esc(item)+'">'+esc(item)+'</a>'
        return '<span>'+esc('Unknown' if item is None else item)+'</span>'
    title=name.replace('-',' ').title()
    if path.suffix=='.json':
        data=json.loads(text)
        body=value(data)+'<details><summary>Original structured data</summary><pre>'+esc(text)+'</pre></details>'
    else:body='<pre>'+esc(text)+'</pre>'
    return '<!doctype html><html><head><meta charset="utf-8"><title>'+esc(title)+'</title><style>body{font:17px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:24px;color:#203840;background:#f5f8fa}dt{font-weight:650;text-transform:capitalize}dd{margin:4px 0 18px 20px}li{margin:14px 0;padding:16px;background:white;border:1px solid #dbe5e9;border-radius:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{overflow-wrap:anywhere}summary{cursor:pointer}</style></head><body><h1>'+esc(title)+'</h1><p>Saved pipeline output. Synthetic customer profiles describe simulated buyers.</p>'+body+'</body></html>'

"""Save before sending; repeated runs reuse responses, not create duplicate requests."""
import json
from pathlib import Path
from customer_simulation.pipeline import read,save
from .policy import expert_policy,feasibility_arguments
from .mcp import tool_data

def request_improvements(plan,out,client):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);policy=expert_policy();results=[]
    product=plan['product']
    for index,improvement in enumerate(plan.get('improvements',plan.get('concerns',[])),1):
        arguments=feasibility_arguments(product,improvement)
        slot=out/f'improvement-{index:02}';slot.mkdir(exist_ok=True)
        request_path=slot/'request.json';response_path=slot/'response.json'
        request={'policy':policy,'expert_brief':improvement['expert_brief'],'title':improvement['title'],'arguments':arguments,
            'source_customer_ids':improvement.get('non_choosing_customer_ids',improvement.get('customer_ids',[]))}
        if request_path.exists():
            if read(request_path)!=request:raise ValueError('Existing feasibility inputs differ; use a fresh output folder')
            if not response_path.exists():raise ValueError('Previous feasibility request has no recorded response; check the Terac dashboard before retrying')
            response=read(response_path)
        else:
            with request_path.open('x') as stream:json.dump(request,stream,indent=2)
            response=client.call('terac_request_feasibility',arguments)
            save(response_path,response)
        data=tool_data(response)
        results.append({'improvement_id':f'improvement-{index:02}','title':improvement['title'],'response':data})
        save(out/'summary.json',{'policy':policy,'requests':results,'studies_launched':0,'experts_hired':0})
    return results

def refresh_improvements(out,client):
    """Read current statuses once. This never resubmits or launches anything."""
    from datetime import datetime,timezone
    out=Path(out);summary=read(out/'summary.json');updated=[]
    for row in summary['requests']:
        slot=out/row['improvement_id'];initial=row['response']
        request_id=initial.get('id')
        if not request_id:raise ValueError('Saved feasibility response has no request ID')
        latest=slot/'latest.json'
        if latest.exists():
            cached=read(latest);value=cached['data'];status=value.get('status')
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(cached['checked_at'])).total_seconds()
            if status in {'RESPONDED','WON','LOST','NOT_PURSUED'} or age<120:
                updated.append({**row,'response':value});continue
        raw=client.call('terac_get_feasibility_request',{'requestId':request_id})
        value=tool_data(raw)
        if value.get('id')!=request_id:raise ValueError('Feasibility response ID mismatch')
        record={'checked_at':datetime.now(timezone.utc).isoformat(),'data':value}
        save(latest,record)
        updated.append({**row,'response':value})
    summary['requests']=updated;save(out/'summary.json',summary)
    return updated

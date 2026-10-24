"""Register reviewed expert scopes locally. Optional refresh/draft creation never launches recruitment."""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend/src'))
from customer_generation.environment import load_environment
from terac_integration.review import register_workspace,ExpertReview
from terac_integration.studies import TeracStudiesMCP

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--concerns',required=True);p.add_argument('--feasibility',required=True);p.add_argument('--workspace',required=True)
    p.add_argument('--refresh',action='store_true');p.add_argument('--create-drafts',action='store_true')
    a=p.parse_args();root=ROOT/'backend/var/expert-review'
    state=register_workspace(root,a.workspace,json.loads(Path(a.concerns).read_text()),json.loads(Path(a.feasibility).read_text()))
    if a.refresh or a.create_drafts:
        load_environment(ROOT/'backend/.env')
        manager=ExpertReview(root,lambda:TeracStudiesMCP(os.environ.get('TERAC_API_KEY')))
        state=manager.refresh(a.workspace)
        if a.create_drafts:state=manager.prepare_drafts(a.workspace)
    print(json.dumps({'workspace':state['id'],'jobs':[{'title':j['scope']['title'],'status':j['status'],'draft_id':j['draft']['id'] if j['draft'] else None,'applicants':len(j['applicants'])} for j in state['jobs']],'launched':False,'invited':False},indent=2))
if __name__=='__main__':main()

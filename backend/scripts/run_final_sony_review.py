"""One final independent review of saved Sony inputs; plan-only unless --execute."""
import argparse,subprocess,sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
SOURCE='sony-compact-20261024-121412-sony-speaker'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true',help='Use only after publishing the calibrated review policy; spends one review call')
    args=p.parse_args()
    prefix='sony-final-'+datetime.now(ZoneInfo('America/New_York')).strftime('%Y%m%d-%H%M%S')
    cmd=[sys.executable,str(ROOT/'backend/scripts/run_smoke_tests.py'),'--model-backend','bridge','--product','sony-speaker',
        '--proposal-format','compact','--reuse-research-run',SOURCE,'--reuse-proposal-run',SOURCE,
        '--max-corrections','0','--run-prefix',prefix]
    if args.execute:cmd.append('--execute')
    raise SystemExit(subprocess.call(cmd,cwd=ROOT))

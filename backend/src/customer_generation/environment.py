"""Explicit dotenv reader: no execution, interpolation, or secret output."""
import os
import re
from pathlib import Path


def load_environment(path,env=None):
    env=os.environ if env is None else env
    values={}
    for number,raw in enumerate(Path(path).read_text().splitlines(),1):
        line=raw.strip()
        if not line or line.startswith('#'):continue
        if line.startswith('export '):line=line[7:]
        key,separator,value=line.partition('=')
        key=key.strip();value=value.strip()
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key):raise ValueError(f'Invalid environment entry on line {number}; use KEY=value')
        if value.startswith(('"',"'")):
            if len(value)<2 or value[-1]!=value[0]:raise ValueError(f'Unclosed environment quote on line {number}')
            value=value[1:-1]
        else:value=value.split(' #',1)[0].rstrip()
        if key in values:raise ValueError(f'Duplicate environment key on line {number}')
        values[key]=value
    # Exported environment wins; an explicit file never overwrites existing keys.
    for key,value in values.items():env.setdefault(key,value)
    return list(values)

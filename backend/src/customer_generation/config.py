"""Explicit environment configuration; no implicit .env loading or live probes."""
import os
from dataclasses import dataclass, field
from .tools.http import validate_endpoint


@dataclass(frozen=True)
class AdapterConfig:
    exa_api_key: str = field(repr=False)
    model_bridge_url: str
    model_bridge_token: str = field(repr=False)
    model_id: str
    max_searches: int = 3
    results_per_search: int = 3
    text_characters_per_source: int = 1200
    search_reserve_usd: float = 0.05
    model_backend: str = "bridge"

    @classmethod
    def from_environment(cls,env=None,*,backend=None):
        env=os.environ if env is None else env
        selected=backend or env.get('MODEL_BACKEND','bridge')
        if selected=='codex':
            from .tools.codex import configured_model
            if not env.get('EXA_API_KEY','').strip():raise ValueError('Missing configuration: EXA_API_KEY')
            config=cls(env['EXA_API_KEY'].strip(),'','',env.get('CODEX_MODEL','').strip() or configured_model(),model_backend='codex')
            config.validate();return config
        if selected=='openrouter':
            required=['EXA_API_KEY','OPENROUTER_API_KEY','OPENROUTER_MODEL']
            if any(not env.get(k,'').strip() for k in required):raise ValueError('Missing configuration: '+', '.join(k for k in required if not env.get(k,'').strip()))
            config=cls(env['EXA_API_KEY'].strip(),'https://openrouter.ai/api/v1/chat/completions',env['OPENROUTER_API_KEY'].strip(),env['OPENROUTER_MODEL'].strip(),model_backend='openrouter')
            config.validate();return config
        if selected!='bridge':raise ValueError('MODEL_BACKEND must be bridge, openrouter or codex')
        names=['EXA_API_KEY','MODEL_BRIDGE_URL','MODEL_BRIDGE_TOKEN','MODEL_ID']
        if any(not env.get(n,'').strip() for n in names):
            missing=', '.join(n for n in names if not env.get(n,'').strip())
            raise ValueError(f'Missing configuration: {missing}')
        config=cls(*(env[n].strip() for n in names))
        config.validate()
        return config

    def validate(self):
        import math
        if self.model_backend not in {'bridge','codex','openrouter'}:raise ValueError('Unsupported model backend')
        if self.model_backend in {'bridge','openrouter'}:validate_endpoint(self.model_bridge_url)
        if not self.exa_api_key.strip() or not self.model_id.strip() or (self.model_backend in {'bridge','openrouter'} and not self.model_bridge_token.strip()):
            raise ValueError('API credentials and model ID must be configured')
        for value,maximum in [(self.max_searches,3),(self.results_per_search,10),(self.text_characters_per_source,4000)]:
            if type(value) is not int or not 1<=value<=maximum:raise ValueError('Invalid research limit')
        if not math.isfinite(self.search_reserve_usd) or self.search_reserve_usd<=0:
            raise ValueError('Search reserve must be positive and finite')

"""Full offline proposal/report fixtures for worker integration tests; no API calls."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'backend/tests')]
from test_concept_simulation import ConceptTests
from customer_simulation.concept import run
from customer_simulation.review_concerns import generate
from customer_generation.tools.llm import ModelBridgeClient
from test_review_concerns import ConcernTransport
case=ConceptTests('test_complete_run_has_conversation_and_separate_checks_without_sidecar')
case.setUp()
try:
    run(case.source,case.root/'worker-fixtures',case.client,count=5)
    concern_transport=ConcernTransport()
    concern_client=ModelBridgeClient('https://offline.example/run','offline-token','offline-model',concern_transport)
    generate(case.root/'worker-fixtures',case.root/'concern-fixtures',concern_client)
    print(json.dumps([{'stage':body['stage'],'payload':body['payload'],'data':data} for body,data in [*case.transport.answers,*concern_transport.answers]]))
finally:case.doCleanups()

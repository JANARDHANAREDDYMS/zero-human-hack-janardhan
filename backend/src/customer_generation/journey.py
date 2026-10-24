"""Local upload -> population -> simulation -> concern generation, no Terac actions."""
from pathlib import Path
from customer_simulation.pipeline import read,save
from .approval import write_summary
from .pipeline import run_generation
from .state import RunLimits,utc_now

class Journey:
    def __init__(self,run_root,simulation_root,backend_factory,client_factory,*,target_count=25,
                 generation=run_generation,simulation=None,concerns=None,guided_flow=False):
        from customer_simulation.concept import run
        from customer_simulation.review_concerns import generate
        self.root=Path(run_root);self.simulations=Path(simulation_root);self.backend_factory=backend_factory;self.client_factory=client_factory
        self.guided_flow=guided_flow
        self.count=target_count;self.generation=generation;self.simulation=simulation or run;self.concerns=concerns or generate

    def paths(self,run_id):
        return self.root/run_id,self.simulations/run_id,self.simulations/run_id/'review-concerns'

    def state_path(self,run_id):return self.root.parent/'journeys'/(run_id+'.json')

    def execute(self,run_id,brief,*,resume=False):
        population,simulation,concerns=self.paths(run_id)
        path=self.state_path(run_id);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            state=read(path)
            if not resume:raise ValueError('Journey exists; explicitly resume it')
        else:state={'run_id':run_id,'guided_flow':self.guided_flow,'status':'running','stage':'research_and_profiles','target_count':self.count,'events':[],
            'outputs':{'generation':str(population),'simulation':str(simulation),'concerns':str(concerns)},
            'terac_actions':False,'generation_status':'pending','simulation_status':'pending','concerns_status':'pending'}
        def update(stage,status='running',**extra):
            state.update(stage=stage,status=status,**extra);state['events'].append({'at':utc_now(),'stage':stage,'status':status});save(path,state)
        try:
            generation_state=population/'state.json'
            if generation_state.exists():
                generation_status=read(generation_state)['status']
                if self.guided_flow and generation_status in {'awaiting_segmentation_approval','running'} and (population/'segmentation-checkpoint.json').exists():
                    if not (population/'segmentation-approval.json').exists():
                        update('segmentation_approval','awaiting_segmentation_approval',generation_status='awaiting_segmentation_approval')
                        return state
                    from .guided import finish_profiles
                    update('profile_generation',generation_status='running')
                    finish_profiles(population)
                elif generation_status!='completed':raise ValueError('Generation did not complete; it cannot be automatically rerun')
            else:
                update('research_and_profiles',generation_status='running')
                # Population directory is reserved by run_generation itself.
                backend=self.backend_factory()
                if self.guided_flow:backend.progress_observer=lambda value:save(population/'research-progress.json',value)
                options={'pause_after_segmentation':True} if self.guided_flow else {}
                result=self.generation(brief,backend,self.root,run_id,target_count=self.count,seed=42,
                    limits=RunLimits(max_tokens_per_call=40000,max_total_tokens=160000,max_cost_usd=1),**options)
                if result.status=='awaiting_segmentation_approval':
                    update('segmentation_approval','awaiting_segmentation_approval',generation_status=result.status)
                    return state
                if result.status!='completed':raise ValueError('Generation did not complete')
            write_summary(population)
            if self.guided_flow:
                authorization=population/'simulation-authorization.json'
                if not authorization.exists():
                    update('simulation_ready','awaiting_simulation',generation_status='completed',error=None)
                    return state
                from .sampling import fingerprint
                hashes={name:fingerprint(read(population/name)) for name in ['customers.json','specification.json','evidence.json']}
                if read(authorization)['input_hashes']!=hashes:raise ValueError('Simulation inputs changed; approve the current profiles before starting')
            update('simulation' ,generation_status='completed',simulation_status='running')
            self.simulation(population,simulation,self.client_factory(),count=self.count,resume=(simulation/'manifest.json').exists())
            update('concerns',simulation_status='completed',concerns_status='running')
            self.concerns(simulation,concerns,self.client_factory(),resume=(concerns/'manifest.json').exists())
            update('completed','completed',concerns_status='completed',error=None)
        except Exception as error:
            # Failure never causes an automatic paid retry. Accepted stage files
            # remain readable even when the next stage stops.
            failed_stage=state['stage']
            stage_key={'profile_generation':'generation_status','research_and_profiles':'generation_status','simulation':'simulation_status','concerns':'concerns_status'}.get(failed_stage)
            extra={stage_key:'failed'} if stage_key else {}
            update(failed_stage,'failed',error={'type':type(error).__name__,
                'message':'This stage stopped. Earlier outputs are saved. Inspect the saved stage files before resuming.'},**extra)
        return state

    def artifacts(self,run_id):
        population,simulation,concerns=self.paths(run_id)
        candidates={'run-details':population/'state.json','population-quality':population/'population-quality.json','profiles':population/'customers.json','evidence':population/'evidence.json','specification':population/'specification.json',
            'generation-summary':population/'population-summary.md','simulation-report':simulation/'report.html',
            'simulation-markdown':simulation/'report.md','simulation-data':simulation/'summary.json',
            'concern-report':concerns/'concerns.html','concern-markdown':concerns/'concerns.md','concern-data':concerns/'concerns.json'}
        return {key:path for key,path in candidates.items() if path.is_file()}

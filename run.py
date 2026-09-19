"""Run reproducible Step-1 experiments and independent seed batches."""
import argparse, hashlib, importlib.metadata, json, os, platform, subprocess
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
import numpy as np
import yaml
from controller import ABCGController
from controller.safety import Safety, is_safe, path_clearances
from environment import Environment
from evaluator import evaluate

STATUSES={'INITIALIZATION_INVALID','BOUNDARY_INVALID','OFFSET_INVALID','CAPACITY_SHORTFALL','PLAN_INVALID',
 'PLAN_SEARCH_EXHAUSTED','TARGET_SEPARATION_INVALID','PATH_UNREACHABLE','NUMERICAL_FAILURE','DEADLOCK',
 'REPLAN_EXHAUSTED','TIMEOUT','COVERAGE_NOT_MET','SAFETY_VIOLATION','SUCCESS'}

def load_config(path,seed=None):
    with Path(path).open(encoding='utf-8') as f: c=yaml.safe_load(f)
    sections={'scene':{'type','width','height','openings'},'crowd':{'count','spawn_vertices','spacing','radius','demand'},
      'guides':{'count','radius','max_speed','initial_inset'},
      'controller':{'method','offset','sample_spacing','budget_gap','max_gap_limit','position_tolerance','speed_tolerance','curve_tolerance','arc_tolerance','safety_numeric_tolerance','demand_bandwidth','gain','hold_steps','clearance','waypoint_tolerance','phases','quadrature_samples','planner_max_iterations','stall_window','max_replans'},
      'simulation':{'seed','dt','max_steps'}}
    if not isinstance(c,dict) or set(c)!={'step',*sections} or c['step']!=1: raise ValueError('Only strict Step-1 schema is supported')
    for s,fields in sections.items():
        if not isinstance(c[s],dict) or set(c[s])!=fields: raise ValueError(f'{s} requires exactly: {sorted(fields)}')
    if seed is not None: c['simulation']['seed']=seed
    ints=[('crowd','count',3),('guides','count',3),('simulation','seed',0),('simulation','max_steps',1),('controller','hold_steps',1),('controller','quadrature_samples',32),('controller','planner_max_iterations',1),('controller','stall_window',2),('controller','max_replans',0)]
    for s,k,m in ints:
        if type(c[s][k]) is not int or c[s][k]<m: raise ValueError(f'{s}.{k} must be integer >= {m}')
    numeric={'scene':['width','height'],'crowd':['spacing'],'guides':['radius','max_speed','initial_inset'],
      'controller':['offset','sample_spacing','budget_gap','max_gap_limit','position_tolerance','speed_tolerance','curve_tolerance','arc_tolerance','safety_numeric_tolerance','demand_bandwidth','gain','clearance','waypoint_tolerance'],'simulation':['dt']}
    for s,keys in numeric.items():
      for k in keys:
        v=c[s][k]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or v<=0: raise ValueError(f'{s}.{k} must be finite positive')
    if c['controller']['method'] not in {'equal_arc','average_cvt','mass_cvt','distmesh'}: raise ValueError('Invalid method')
    if not isinstance(c['controller']['phases'],list) or not c['controller']['phases'] or not np.isfinite(c['controller']['phases']).all(): raise ValueError('phases must be a nonempty finite list')
    for name in ['radius','demand']:
      if set(c['crowd'][name])!={'mean','std','min','max'}: raise ValueError(f'Invalid crowd.{name}')
    if c['simulation']['dt']*c['controller']['gain']>1: raise ValueError('Conservative tracker requires dt * gain <= 1')
    return c

def _provenance(config,obs):
    def cmd(*args):
      try:return subprocess.check_output(args,text=True,stderr=subprocess.DEVNULL).strip()
      except:return None
    raw=np.ascontiguousarray(np.c_[obs.positions,obs.radii,obs.demand]).tobytes()
    deps={x:importlib.metadata.version(x) for x in ['numpy','scipy','shapely','PyYAML','jupedsim']}
    return {'commit':cmd('git','rev-parse','HEAD'),'dirty':bool(cmd('git','status','--porcelain')),
      'input_snapshot_sha256':hashlib.sha256(raw).hexdigest(),'config_sha256':hashlib.sha256(yaml.safe_dump(config,sort_keys=True).encode()).hexdigest(),
      'python':platform.python_version(),'platform':platform.platform(),'dependencies':deps}

def experiment(config_path,output,seed=None,plots=True):
    started=perf_counter(); config=load_config(config_path,seed); output=Path(output)
    if output.exists() and any(output.iterdir()): raise FileExistsError(f'Use an empty output directory: {output}')
    output.mkdir(parents=True,exist_ok=True); (output/'state.json').write_text('{"status":"started"}\n')
    env=Environment(config); obs=env.observe(); initial=env.initialize_guides(config['guides']); c=config['controller']; sim=config['simulation']; g=config['guides']
    safety=Safety(2*g['radius']+c['clearance'],g['radius']+float(obs.radii.max())+c['clearance'],g['radius']+c['clearance'],g['max_speed'],c['safety_numeric_tolerance'])
    ctrl=ABCGController(c,safety,env.scene.size); positions=[initial]; nominal=[]; executed=[]; safety_log=[]
    termination='TIMEOUT'; failure_reason=''; failure_stage='execution'; hold=0; deadlocks=[]
    try:
      if not is_safe(path_clearances(initial,initial,obs.positions,env.scene.size),safety): raise ValueError('INITIALIZATION_INVALID: unsafe guide start')
      failure_stage='planning'; ctrl.prepare(obs,initial); failure_stage='execution'
      progress=[]
      for step in range(sim['max_steps']):
        nom,result=ctrl.step(env.observe(),positions[-1],sim['dt']); nxt=positions[-1]+sim['dt']*result.velocity
        if not is_safe(path_clearances(positions[-1],nxt,obs.positions,env.scene.size),safety): raise ValueError('SAFETY_VIOLATION: candidate segment rejected before execution')
        nominal.append(nom); executed.append(result.velocity); positions.append(nxt); env.advance(sim['dt'])
        safety_log.append({k:(v.item() if isinstance(v,np.generic) else v) for k,v in asdict(result).items() if k!='velocity'})
        err=ctrl.errors(nxt); progress.append(float(err.sum()))
        settled=np.all(err<=c['position_tolerance']) and np.max(np.linalg.norm(result.velocity,axis=1))<=c['speed_tolerance']
        hold=hold+1 if settled else 0
        if hold>=c['hold_steps']: termination='COVERAGE_NOT_MET'; break
        if len(progress)>=c['stall_window'] and progress[-c['stall_window']]-progress[-1] < c['position_tolerance'] and not settled:
          deadlocks.append({'step':step,'progress':progress[-1],'strategy':'bounded stop'})
          termination='REPLAN_EXHAUSTED'; failure_reason='No path progress within configured window; bounded recovery exhausted'; break
    except ValueError as e:
      failure_reason=str(e); termination=failure_reason.split(':')[0]
      if termination not in STATUSES: raise
    trajectory=np.asarray(positions); velocities=np.asarray(executed).reshape(-1,len(initial),2); active=ctrl.assignment>=0 if ctrl.assignment is not None else np.zeros(len(initial),bool)
    eval_cfg=dict(c,_people=obs.positions,_room=env.scene.size)
    criteria,diagnostics=evaluate(trajectory,velocities,active,ctrl.plan.positions if ctrl.plan else np.empty((0,2)),ctrl.assignment if ctrl.assignment is not None else np.full(len(initial),-1),ctrl.boundary,safety,eval_cfg)
    success=all(criteria.values())
    if success: termination='SUCCESS'; failure_reason=''; failure_stage=None
    elif termination=='COVERAGE_NOT_MET': failure_reason='Terminal motion condition reached, but independent acceptance criteria were not all satisfied'
    metrics={'schema_version':'1.0.0',**_provenance(config,obs),'scene':env.scene.name,'method':c['method'],'seed':sim['seed'],
      'termination_status':termination,'motion_status':'CONVERGED' if hold>=c['hold_steps'] else 'STOPPED' if termination!='TIMEOUT' else 'TRACKING',
      'failure_reason':failure_reason,'failure_stage':failure_stage,'success':success,'criteria':criteria,'active_guides':int(active.sum()),'reserve_guides':int((~active).sum()),
      'steps':len(executed),'simulation_time':len(executed)*sim['dt'],'wall_time':perf_counter()-started,
      'curve_length':None if ctrl.boundary is None else ctrl.boundary.length,'planned_max_gap':None if ctrl.plan is None else ctrl.plan.max_gap,'max_gap_limit':c['max_gap_limit'],
      'target_min_euclidean_distance':None if ctrl.plan is None else float(np.min(np.linalg.norm(ctrl.plan.positions[:,None]-ctrl.plan.positions[None,:]+np.eye(len(ctrl.plan.positions))[:,:,None]*1e9,axis=2))),
      **diagnostics,'planning_attempts':ctrl.attempts,'total_demand':float(obs.demand.sum()),'safety_limits':asdict(safety),'safety_diagnostics':safety_log,
      'fallback_count':sum(x['fallback_used'] for x in safety_log),'replan_count':ctrl.replans,'deadlock_events':deadlocks,'crowd_static':bool(np.array_equal(obs.positions,env.observe().positions))}
    (output/'metrics.json').write_text(json.dumps(metrics,indent=2,allow_nan=False)+'\n'); (output/'config.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    np.savez_compressed(output/'trajectory.npz',time=np.arange(len(positions))*sim['dt'],positions=trajectory,nominal_velocity=np.asarray(nominal).reshape(-1,len(initial),2),safe_velocity=velocities,active_mask=active,targets=ctrl.plan.positions if ctrl.plan else np.empty((0,2)),assignment=ctrl.assignment if ctrl.assignment is not None else np.full(len(initial),-1),crowd_positions=obs.positions,crowd_radii=obs.radii,crowd_demand=obs.demand)
    (output/'planning.json').write_text(json.dumps(ctrl.attempts,indent=2)+'\n'); (output/'state.json').write_text(json.dumps({'status':'completed','success':success})+'\n')
    if plots:
      from visualization import plot_result; plot_result(env,trajectory,ctrl,metrics,output/'scene.png')
    return metrics

def _worker(a):
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1): return experiment(*a)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--config',required=True); p.add_argument('--output',required=True); x=p.add_mutually_exclusive_group(); x.add_argument('--seed',type=int); x.add_argument('--seeds',type=int,nargs='+'); p.add_argument('--workers',default='auto'); p.add_argument('--no-plots',action='store_true'); a=p.parse_args()
    if a.seeds is None: print(json.dumps(experiment(a.config,a.output,a.seed,not a.no_plots),indent=2)); return
    if min(a.seeds)<0 or len(a.seeds)!=len(set(a.seeds)): p.error('Seeds must be distinct nonnegative integers')
    available=len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count() or 1; workers=min(available if a.workers=='auto' else int(a.workers),len(a.seeds)); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    tasks=[(a.config,out/f'seed_{s}',s,not a.no_plots) for s in a.seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool: results=list(pool.map(_worker,tasks))
    summary={'runs':len(results),'successful':sum(r['success'] for r in results),'workers':workers,'failure_reasons':{s:sum(r['termination_status']==s for r in results) for s in sorted(STATUSES)}}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary))
if __name__=='__main__': main()

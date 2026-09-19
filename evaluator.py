"""Controller-independent evaluation from saved execution data."""
import numpy as np
from shapely.geometry import LineString, Point
from controller.safety import path_clearances


def evaluate(trajectory, velocities, active, targets, assignment, boundary, safety, cfg, planned_ok=True, path_ok=True):
    names=['geometry_ok','resource_ok','plan_ok','path_ok','safety_ok','arrival_ok','curve_ok','gap_ok','coverage_ok']
    criteria={k:False for k in names}
    if boundary is None or not active.any() or len(targets)==0:
        return criteria, {}
    line=LineString(np.vstack([boundary.deployment,boundary.deployment[0]]))
    selected=trajectory[:,active]; assigned=targets[assignment[active]]
    errors=np.linalg.norm(selected-assigned[None,:,:],axis=2)
    curve=np.array([[line.distance(Point(p)) for p in frame] for frame in selected])
    arcs=np.array([[line.project(Point(p)) for p in frame] for frame in selected])
    gaps=np.array([np.diff(np.r_[np.sort(a),np.sort(a)[0]+line.length]).max() for a in arcs])
    speeds=np.linalg.norm(velocities[:,active],axis=2) if len(velocities) else np.empty((0,active.sum()))
    safe=True; minima={'crowd':np.inf,'guides':np.inf,'walls':np.inf}; dangerous={k:None for k in minima}
    for k in range(len(trajectory)-1):
        c=path_clearances(trajectory[k],trajectory[k+1],cfg['_people'],cfg['_room'])
        for key,val in c.items():
            if val is not None and val<minima[key]: minima[key]=val; dangerous[key]=k
        safe &= c['crowd']>=safety.crowd_distance-safety.numeric_tolerance and c['walls']>=safety.wall_distance-safety.numeric_tolerance and (c['guides'] is None or c['guides']>=safety.guide_distance-safety.numeric_tolerance)
    h=cfg['hold_steps']; enough=len(trajectory)>=h+1 and len(velocities)>=h
    terminal_arrival=enough and np.all(errors[-h:]<=cfg['position_tolerance']) and np.all(speeds[-h:]<=cfg['speed_tolerance'])
    terminal_curve=enough and np.all(curve[-h:]<=cfg['curve_tolerance'])
    terminal_gap=enough and np.all(gaps[-h:]<=cfg['max_gap_limit'])
    criteria.update(geometry_ok=True,resource_ok=True,plan_ok=planned_ok,path_ok=path_ok,safety_ok=bool(safe),
                    arrival_ok=bool(terminal_arrival),curve_ok=bool(terminal_curve),gap_ok=bool(terminal_gap))
    criteria['coverage_ok']=criteria['curve_ok'] and criteria['gap_ok']
    order=np.argsort(assignment[active]); ordered=np.unwrap(arcs[-1,order]*2*np.pi/line.length)
    diag={'tracking_rmse':float(np.sqrt(np.mean(errors[-1]**2))),'max_tracking_error':float(errors[-1].max()),
          'mean_curve_distance':float(curve[-1].mean()),'max_curve_distance':float(curve[-1].max()),
          'actual_max_gap':float(gaps[-1]),'arc_projection_error_max':float(np.max(np.abs(((arcs[-1]-np.array([line.project(Point(p)) for p in assigned])+line.length/2)%line.length)-line.length/2))),
          'projection_valid':True,'order_preserved':bool(np.all(np.diff(ordered)>=-1e-8)),
          'minimum_center_distances':{k:(None if not np.isfinite(v) else float(v)) for k,v in minima.items()},'most_dangerous_step':dangerous}
    return criteria,diag

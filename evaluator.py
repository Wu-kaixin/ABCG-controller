"""Controller-independent evaluation from saved execution data."""
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from controller.navigation import route_assigned
from controller.safety import path_clearances


def evaluate(trajectory, velocities, active, targets, assignment, boundary, safety, cfg,
             planned_ok=True, path_ok=True):
    names=['geometry_ok','resource_ok','plan_ok','path_ok','safety_ok','arrival_ok','curve_ok','gap_ok','coverage_ok']
    criteria={k:False for k in names}
    if boundary is None or not active.any() or len(targets)==0:
        return criteria, {}
    deployment=Polygon(boundary.deployment)
    crowd=Polygon(boundary.crowd)
    line=deployment.exterior
    people=np.asarray(cfg['_people'])
    radii=np.asarray(cfg.get('_radii',np.zeros(len(people))))
    room=np.asarray(cfg['_room'])
    geometry=(deployment.is_valid and crowd.is_valid and deployment.area>0 and crowd.area>0
              and np.isfinite(boundary.deployment).all()
              and np.all(boundary.deployment>=safety.wall_distance-safety.numeric_tolerance)
              and np.all(boundary.deployment<=room-safety.wall_distance+safety.numeric_tolerance)
              and all(crowd.covers(Point(p).buffer(float(r),quad_segs=16))
                      for p,r in zip(people,radii)))
    ids=assignment[active]
    resource=(active.sum()==len(targets) and len(ids)==len(targets)
              and np.array_equal(np.sort(ids),np.arange(len(targets))))
    target_curve=np.array([line.distance(Point(p)) for p in targets])
    target_arcs=np.sort(np.array([line.project(Point(p)) for p in targets]))
    target_gap=float(np.diff(np.r_[target_arcs,target_arcs[0]+line.length]).max())
    target_dist=np.linalg.norm(targets[:,None]-targets[None,:],axis=2)
    np.fill_diagonal(target_dist,np.inf)
    plan=(np.isfinite(targets).all() and np.all(target_curve<=1e-7)
          and target_gap<=cfg['max_gap_limit']-2*cfg.get('arc_tolerance',0.)+1e-8
          and float(target_dist.min())>=safety.guide_distance-safety.numeric_tolerance)
    reachable=False
    if resource:
        try:
            route_assigned(trajectory[0],targets,assignment,room,safety.wall_distance,
                           crowd,safety.wall_distance)
            reachable=True
        except ValueError:
            reachable=False
    selected=trajectory[:,active]; assigned=targets[assignment[active]]
    errors=np.linalg.norm(selected-assigned[None,:,:],axis=2)
    curve=np.array([[line.distance(Point(p)) for p in frame] for frame in selected])
    arcs=np.array([[line.project(Point(p)) for p in frame] for frame in selected])
    gaps=np.array([np.diff(np.r_[np.sort(a),np.sort(a)[0]+line.length]).max() for a in arcs])
    speeds=np.linalg.norm(velocities[:,active],axis=2) if len(velocities) else np.empty((0,active.sum()))
    safe=True; minima={'crowd':np.inf,'guides':np.inf,'walls':np.inf}; dangerous={k:None for k in minima}
    for k in range(len(trajectory)-1):
        c=path_clearances(trajectory[k],trajectory[k+1],people,room)
        for key,val in c.items():
            if val is not None and val<minima[key]: minima[key]=val; dangerous[key]=k
        safe &= c['crowd']>=safety.crowd_distance-safety.numeric_tolerance and c['walls']>=safety.wall_distance-safety.numeric_tolerance and (c['guides'] is None or c['guides']>=safety.guide_distance-safety.numeric_tolerance)
    h=cfg['hold_steps']; enough=len(trajectory)>=h+1 and len(velocities)>=h
    terminal_arrival=enough and np.all(errors[-h:]<=cfg['position_tolerance']) and np.all(speeds[-h:]<=cfg['speed_tolerance'])
    terminal_curve=enough and np.all(curve[-h:]<=cfg['curve_tolerance'])
    terminal_gap=enough and np.all(gaps[-h:]<=cfg['max_gap_limit'])
    criteria.update(geometry_ok=bool(geometry),resource_ok=bool(resource),
                    plan_ok=bool(plan and planned_ok),path_ok=bool(reachable and path_ok),safety_ok=bool(safe),
                    arrival_ok=bool(terminal_arrival),curve_ok=bool(terminal_curve),gap_ok=bool(terminal_gap))
    criteria['coverage_ok']=criteria['curve_ok'] and criteria['gap_ok']
    order=np.argsort(assignment[active]); ordered=np.unwrap(arcs[-1,order]*2*np.pi/line.length)
    net={'crowd':minima['crowd']-safety.crowd_distance,
         'guides':None if not np.isfinite(minima['guides']) else minima['guides']-safety.guide_distance,
         'walls':minima['walls']-safety.wall_distance}
    diag={'tracking_rmse':float(np.sqrt(np.mean(errors[-1]**2))),'max_tracking_error':float(errors[-1].max()),
          'mean_curve_distance':float(curve[-1].mean()),'max_curve_distance':float(curve[-1].max()),
          'actual_max_gap':float(gaps[-1]),'arc_projection_error_max':float(np.max(np.abs(((arcs[-1]-np.array([line.project(Point(p)) for p in assigned])+line.length/2)%line.length)-line.length/2))),
          'projection_valid':True,'order_preserved':bool(np.all(np.diff(ordered)>=-1e-8)),
          'target_actual_max_gap':target_gap,
          'minimum_center_distances':{k:(None if not np.isfinite(v) else float(v)) for k,v in minima.items()},
          'minimum_net_clearances':{k:(None if v is None or not np.isfinite(v) else float(v)) for k,v in net.items()},
          'most_dangerous_step':dangerous}
    return criteria,diag

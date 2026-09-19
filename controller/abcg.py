"""ABCG planning, reachable assignment, waypoint tracking and safe feedback."""
import numpy as np
from shapely.geometry import Polygon

from .boundary import estimate_boundary
from .coverage import plan_coverage
from .navigation import navigate_and_assign
from .safety import safe_velocity


class ABCGController:
    def __init__(self, config, safety, room):
        self.config=config; self.safety=safety; self.room=np.asarray(room,float)
        self.boundary=self.plan=self.assignment=None
        self.attempts=[]; self.paths={}; self.waypoint={}; self.replans=0

    def prepare(self, observation, guides):
        c=self.config
        self.boundary=estimate_boundary(observation.positions,c['offset'],c['sample_spacing'],self.room,
            self.safety.wall_distance,self.safety.crowd_distance,observation.radii)
        planned_limit=c['max_gap_limit']-2*c['arc_tolerance']
        if planned_limit <= 0: raise ValueError('PLAN_INVALID: max_gap_limit - 2*arc_tolerance must be positive')
        lower=max(3,int(np.ceil(self.boundary.length/planned_limit)))
        start=max(3,int(np.ceil(self.boundary.length/c['budget_gap'])))
        if lower > len(guides):
            raise ValueError(f'CAPACITY_SHORTFALL: necessary planning bound requires {lower}, have {len(guides)}')
        chosen=None
        # Search every N: the budget recommendation must not suppress a smaller feasible N.
        order=list(range(lower,len(guides)+1)); order.sort(key=lambda n:(n<start,abs(n-start)))
        for n in order:
            for phase in c['phases']:
                plan=plan_coverage(self.boundary,observation.positions,observation.demand,n,
                    c['demand_bandwidth'],c['method'],phase,c['quadrature_samples'],c['planner_max_iterations'])
                distances=np.linalg.norm(plan.positions[:,None]-plan.positions[None,:],axis=2)
                np.fill_diagonal(distances,np.inf); separation=float(distances.min())
                accepted=plan.max_gap <= planned_limit+1e-9 and separation >= self.safety.guide_distance
                self.attempts.append({'n':n,'phase':phase,'max_gap':plan.max_gap,'min_separation':separation,
                    'cost':plan.cost.tolist(),'iterations':plan.iterations,'exit_reason':plan.exit_reason,'accepted':accepted})
                if accepted: chosen=plan; break
            if chosen is not None: break
        if chosen is None: raise ValueError('PLAN_SEARCH_EXHAUSTED: bounded CVT/spacing search found no admissible target set')
        self.plan=chosen
        crowd=Polygon(self.boundary.crowd)
        nav=navigate_and_assign(guides,chosen.positions,self.room,self.safety.wall_distance,
                                crowd,self.safety.crowd_distance)
        self.assignment=nav.assignment
        for guide,(path,length) in zip(np.flatnonzero(nav.assignment>=0),zip(nav.paths,nav.lengths)):
            self.paths[int(guide)]=path; self.waypoint[int(guide)]=1
        self.navigation=nav

    def errors(self, positions):
        active=self.assignment>=0
        vectors=self.plan.positions[self.assignment[active]]-positions[active]
        return np.linalg.norm(vectors,axis=1)

    def step(self, observation, positions, dt):
        nominal=np.zeros_like(positions)
        for i in np.flatnonzero(self.assignment>=0):
            path=self.paths[int(i)]; k=self.waypoint[int(i)]
            while k < len(path)-1 and np.linalg.norm(path[k]-positions[i]) <= self.config['waypoint_tolerance']:
                k+=1
            self.waypoint[int(i)]=k
            nominal[i]=self.config['gain']*(path[k]-positions[i])
        speed=np.linalg.norm(nominal,axis=1)
        nominal*=np.minimum(1.,self.safety.max_speed/np.maximum(speed,1e-30))[:,None]
        return nominal,safe_velocity(positions,nominal,observation.positions,self.room,dt,self.safety)

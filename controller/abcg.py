"""ABCG planning, reachable assignment, waypoint tracking and safe feedback."""
import numpy as np
from shapely.geometry import Polygon

from .boundary import estimate_boundary
from .coverage import plan_coverage
from .navigation import navigate_and_assign, route_assigned
from .safety import safe_velocity


class ABCGController:
    def __init__(self, config, safety, room, protocol='adaptive_resource', fixed_n=None):
        self.config=config; self.safety=safety; self.room=np.asarray(room,float)
        self.boundary=self.plan=self.assignment=None
        self.attempts=[]; self.paths={}; self.waypoint={}; self.replans=0
        self.protocol=protocol; self.fixed_n=fixed_n
        self.priority_order=[]; self.priority_index=0; self.priority_mode=False
        self._observation=None

    def _install_navigation(self, nav):
        self.assignment=nav.assignment
        self.paths={}; self.waypoint={}
        active=np.flatnonzero(nav.assignment>=0)
        for guide,path in zip(active,nav.paths):
            self.paths[int(guide)]=path
            self.waypoint[int(guide)]=1
        self.navigation=nav

    def prepare(self, observation, guides):
        c=self.config
        self._observation=observation
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
        if self.protocol == 'fixed_n':
            if type(self.fixed_n) is not int or self.fixed_n < 3:
                raise ValueError('PLAN_INVALID: fixed_n protocol requires integer fixed_n >= 3')
            if self.fixed_n > len(guides):
                raise ValueError(f'CAPACITY_SHORTFALL: fixed_n requires {self.fixed_n}, have {len(guides)}')
            order=[self.fixed_n]
        elif self.protocol == 'adaptive_resource':
            order=list(range(lower,len(guides)+1)); order.sort(key=lambda n:(n<start,abs(n-start)))
        else:
            raise ValueError(f'PLAN_INVALID: unsupported protocol {self.protocol}')
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
                                crowd,self.safety.wall_distance)
        self._install_navigation(nav)

    def errors(self, positions):
        active=self.assignment>=0
        vectors=self.plan.positions[self.assignment[active]]-positions[active]
        return np.linalg.norm(vectors,axis=1)

    def remaining_path_lengths(self, positions):
        """Remaining polyline distance; unlike target distance it decreases on detours."""
        remaining=[]
        for i in np.flatnonzero(self.assignment>=0):
            path=self.paths[int(i)]; k=self.waypoint[int(i)]
            value=float(np.linalg.norm(path[k]-positions[i]))
            if k < len(path)-1:
                value += float(np.linalg.norm(np.diff(path[k:],axis=0),axis=1).sum())
            remaining.append(value)
        return np.asarray(remaining)

    def recover(self, observation, positions):
        """Finite deterministic recovery: reroute, reassign, then priority yield."""
        if self.replans >= self.config['max_replans']:
            return None
        strategy=('path_recompute','reachable_reassignment','priority_yield')[min(self.replans,2)]
        crowd=Polygon(self.boundary.crowd)
        if strategy == 'path_recompute':
            paths,_=route_assigned(positions,self.plan.positions,self.assignment,self.room,
                                   self.safety.wall_distance,crowd,self.safety.wall_distance)
            self.paths=paths; self.waypoint={i:1 for i in paths}
        elif strategy == 'reachable_reassignment':
            nav=navigate_and_assign(positions,self.plan.positions,self.room,
                                    self.safety.wall_distance,crowd,self.safety.wall_distance)
            self._install_navigation(nav)
        else:
            active=np.flatnonzero(self.assignment>=0)
            remaining=self.remaining_path_lengths(positions)
            self.priority_order=[int(active[k]) for k in np.argsort(-remaining,kind='stable')]
            self.priority_index=0; self.priority_mode=True
        self.replans += 1
        return strategy

    def step(self, observation, positions, dt):
        nominal=np.zeros_like(positions)
        priority=None
        if self.priority_mode and self.priority_order:
            while self.priority_index < len(self.priority_order):
                candidate=self.priority_order[self.priority_index]
                target=self.plan.positions[self.assignment[candidate]]
                if np.linalg.norm(target-positions[candidate]) <= self.config['position_tolerance']:
                    self.priority_index += 1
                else:
                    priority=candidate; break
            if self.priority_index >= len(self.priority_order):
                self.priority_mode=False
        for i in np.flatnonzero(self.assignment>=0):
            if priority is not None and i != priority:
                continue
            path=self.paths[int(i)]; k=self.waypoint[int(i)]
            while k < len(path)-1 and np.linalg.norm(path[k]-positions[i]) <= self.config['waypoint_tolerance']:
                k+=1
            self.waypoint[int(i)]=k
            nominal[i]=self.config['gain']*(path[k]-positions[i])
        speed=np.linalg.norm(nominal,axis=1)
        nominal*=np.minimum(1.,self.safety.max_speed/np.maximum(speed,1e-30))[:,None]
        return nominal,safe_velocity(positions,nominal,observation.positions,self.room,dt,self.safety)

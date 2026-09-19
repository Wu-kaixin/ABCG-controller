"""Adversarial acceptance, planning and navigation checks."""
from types import SimpleNamespace
import numpy as np
import pytest
from shapely.geometry import Polygon

from controller.boundary import Boundary
from controller.coverage import plan_coverage
from controller.navigation import navigate_and_assign
from controller.safety import Safety
from evaluator import evaluate


def circle_boundary(n=256, radius=4.):
    theta=np.arange(n)*2*np.pi/n; points=np.c_[10+radius*np.cos(theta),10+radius*np.sin(theta)]
    lengths=np.linalg.norm(np.roll(points,-1,axis=0)-points,axis=1)
    return Boundary(points.copy(),points,np.r_[0.,np.cumsum(lengths[:-1])],float(lengths.sum()))


def eval_case(final, targets, velocities, **overrides):
    b=circle_boundary(); trajectory=np.stack([final,final]); active=np.ones(len(final),bool); assignment=np.arange(len(final))
    cfg={'hold_steps':1,'position_tolerance':.1,'speed_tolerance':.1,'curve_tolerance':.1,
         'max_gap_limit':9.,'_people':np.array([[10.,10.]]),'_room':np.array([20.,20.])}|overrides
    return evaluate(trajectory,velocities,active,targets,assignment,b,Safety(.2,.2,.1,1.),cfg)[0]


def test_arrived_but_gap_limit_fails():
    b=circle_boundary(); targets=b.deployment[[0,10,128]]
    c=eval_case(targets,targets,np.zeros((1,3,2)),max_gap_limit=3.)
    assert c['arrival_ok'] and not c['gap_ok'] and not c['coverage_ok']


def test_small_projected_gap_but_far_from_curve_fails():
    b=circle_boundary(); targets=b.deployment[[0,64,128,192]]; final=targets+(targets-np.array([10,10]))*.5
    c=eval_case(final,final,np.zeros((1,4,2)),curve_tolerance=.1)
    assert not c['curve_ok'] and not c['coverage_ok']


def test_rmse_cannot_hide_one_large_error_and_zero_speed_is_not_arrival():
    b=circle_boundary(); targets=b.deployment[[0,64,128,192]]; final=targets.copy(); final[0]+=[.2,0]
    assert not eval_case(final,targets,np.zeros((1,4,2)))['arrival_ok']
    assert not eval_case(targets+1,targets,np.zeros((1,4,2)))['arrival_ok']


def test_hold_window_and_historical_safety_are_required():
    b=circle_boundary(); targets=b.deployment[[0,64,128,192]]
    cfg={'hold_steps':2,'position_tolerance':.1,'speed_tolerance':.1,'curve_tolerance':.1,'max_gap_limit':9.,'_people':np.array([[10.,10.]]),'_room':np.array([20.,20.])}
    c,_=evaluate(np.stack([targets,targets]),np.zeros((1,4,2)),np.ones(4,bool),targets,np.arange(4),b,Safety(.2,.2,.1,1.),cfg)
    assert not c['arrival_ok']
    unsafe=np.stack([targets,targets]); unsafe[0,0]=unsafe[0,1]
    c,_=evaluate(unsafe,np.zeros((1,4,2)),np.ones(4,bool),targets,np.arange(4),b,Safety(.2,.2,.1,1.),cfg|{'hold_steps':1})
    assert not c['safety_ok']


def test_empty_plan_is_structured_failure():
    c,d=evaluate(np.zeros((1,2,2)),np.empty((0,2,2)),np.zeros(2,bool),np.empty((0,2)),np.full(2,-1),None,Safety(.2,.2,.1,1.),{'hold_steps':1})
    assert not any(c.values()) and d == {}


@pytest.mark.parametrize('method', ['equal_arc','average_cvt','mass_cvt','distmesh'])
def test_all_methods_produce_finite_periodic_plan(method):
    b=circle_boundary(); people=np.array([[8.,10.],[12.,10.]])
    p=plan_coverage(b,people,np.array([1.,2.]),12,1.,method)
    assert np.isfinite(p.positions).all() and p.max_gap>0 and len(p.cost)>=1
    if method in {'average_cvt','mass_cvt'}: assert np.all(np.diff(p.cost)<=1e-9)


def test_mass_scaling_does_not_change_sites_and_high_demand_tightens_spacing():
    b=circle_boundary(); people=np.array([[14.,10.],[6.,10.]])
    one=plan_coverage(b,people,np.array([8.,1.]),12,1.,'mass_cvt')
    scaled=plan_coverage(b,people,np.array([80.,10.]),12,1.,'mass_cvt')
    np.testing.assert_allclose(one.arc_positions,scaled.arc_positions,atol=2e-3)
    high=np.sort(one.arc_positions[one.arc_positions < b.length*.25])
    low=np.sort(one.arc_positions[(one.arc_positions>b.length*.5)&(one.arc_positions<b.length*.75)])
    assert len(high)>=len(low)


def test_visibility_navigation_routes_around_obstacle_and_detects_unreachable():
    crowd=Polygon([(4,3),(6,3),(6,7),(4,7)])
    result=navigate_and_assign(np.array([[2.,5.]]),np.array([[8.,5.]]),np.array([10.,10.]),.1,crowd,.2)
    assert len(result.paths[0])>2 and result.lengths[0]>6
    with pytest.raises(ValueError,match='PATH_UNREACHABLE'):
        navigate_and_assign(np.array([[2.,5.]]),np.array([[5.,5.]]),np.array([10.,10.]),.1,crowd,.2)

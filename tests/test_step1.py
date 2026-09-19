"""Essential checks for geometry, frozen observations, control and failure states."""
from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest
import yaml

from controller.boundary import estimate_boundary
from controller.coverage import plan_coverage
from controller.safety import Safety, is_safe, path_clearances, safe_velocity
from environment import Environment
from interfaces import Observation
from run import experiment, load_config, reevaluate_result
from scene import build_scene

ROOT = Path(__file__).resolve().parents[1]


def config(name='square'):
    return load_config(ROOT/f'configs/step1/{name}.yaml')


def write_config(tmp_path, value):
    path = tmp_path/'case.yaml'
    path.write_text(yaml.safe_dump(value), encoding='utf-8')
    return path


def test_static_observation_contains_no_spawn_geometry():
    env = Environment(config())
    original = env.observe()
    env.advance(.1)
    np.testing.assert_array_equal(env.observe().positions, original.positions)
    original.positions[:] = 0
    assert np.any(env.observe().positions != 0)
    assert {field.name for field in fields(Observation)} == {'positions', 'radii', 'demand'}
    distances = np.linalg.norm(env.observe().positions[:, None]-env.observe().positions[None], axis=2)
    np.fill_diagonal(distances, np.inf)
    assert np.all(distances >= env.observe().radii[:, None]+env.observe().radii[None])


def test_deployment_length_matches_its_actual_polyline():
    points = np.array([[3., 3.], [5., 3.], [5., 5.], [3., 5.]])
    result = estimate_boundary(points, 1., .1, np.array([10., 10.]), .2, .5)
    length = np.linalg.norm(np.roll(result.deployment, -1, axis=0)-result.deployment, axis=1).sum()
    assert result.length == pytest.approx(length)
    assert result.length > 8+6
    assert np.all(np.diff(result.arc) > 0)


def test_demand_changes_targets_and_lloyd_cost_decreases():
    people = np.array([[3., 3.], [5., 3.], [5., 5.], [3., 5.]])
    boundary = estimate_boundary(people, 1., .1, np.array([10., 10.]), .2, .5)
    uniform = plan_coverage(boundary, people, np.ones(4), 8, .8)
    weighted = plan_coverage(boundary, people, np.array([.75, 1.25, 1.25, .75]), 8, .8)
    assert not np.allclose(uniform.positions, weighted.positions)
    assert np.all(np.diff(weighted.cost) <= 1e-9)


def test_filter_prevents_an_intermediate_guide_collision():
    guides = np.array([[1., 2.], [3., 2.]])
    nominal = np.array([[2., 0.], [-2., 0.]])
    people, room = np.array([[4., 4.]]), np.array([5., 5.])
    limits = Safety(.6, .6, .2, 2.)
    assert not is_safe(path_clearances(guides, guides+nominal, people, room), limits)
    result = safe_velocity(guides, nominal, people, room, 1., limits)
    assert is_safe(path_clearances(guides, guides+result.velocity, people, room), limits)
    assert np.linalg.norm(result.velocity, axis=1).max() <= 2.+1e-9
    assert result.status == 'SOLVED'


@pytest.mark.parametrize('name', ['square', 'rectangle'])
def test_default_scene_runs(tmp_path, name):
    metrics = experiment(ROOT/f'configs/step1/{name}.yaml', tmp_path/name, plots=False)
    assert metrics['success']
    assert metrics['crowd_static']
    assert metrics['termination_status'] == 'SUCCESS'
    assert all(metrics['criteria'].values())
    assert metrics['steps'] > 10
    assert metrics['tracking_rmse'] < .03
    assert metrics['replan_count'] == 0
    trace = np.load(tmp_path/name/'trajectory.npz')
    assert len(trace['positions']) == len(trace['safe_velocity'])+1


@pytest.mark.parametrize('case,status', [('capacity', 'CAPACITY_SHORTFALL'), ('offset', 'OFFSET_INVALID'), ('timeout', 'TIMEOUT')])
def test_failure_states_remain_failures(tmp_path, case, status):
    cfg = config()
    if case == 'capacity':
        cfg['guides']['count'] = 3
    elif case == 'offset':
        cfg['controller']['offset'] = 20
    else:
        cfg['simulation']['max_steps'] = 1
    result = experiment(write_config(tmp_path, cfg), tmp_path/'out', plots=False)
    assert result['termination_status'] == status
    assert not result['success']


def test_configuration_rejects_unsupported_scope_and_typo(tmp_path):
    cfg = config()
    cfg['step'] = 2
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, cfg))
    cfg = config()
    cfg['controller']['gaim'] = 2
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, cfg))
    cfg = config()
    cfg['scene']['openings'] = [{'wall': 'top', 'start': 1, 'end': 2}]
    with pytest.raises(ValueError):
        build_scene(cfg['scene'])


def test_repeatability_and_output_protection(tmp_path):
    first, second = Environment(config()), Environment(config())
    np.testing.assert_array_equal(first.observe().positions, second.observe().positions)
    np.testing.assert_array_equal(first.observe().demand, second.observe().demand)
    path = tmp_path/'output'
    path.mkdir()
    (path/'existing').write_text('keep')
    with pytest.raises(FileExistsError):
        experiment(ROOT/'configs/step1/square.yaml', path, plots=False)
    assert (path/'existing').read_text() == 'keep'


def test_initialization_failure_is_structured(tmp_path):
    cfg=config(); cfg['crowd']['radius']['min']=-1
    output=tmp_path/'invalid'
    result=experiment(write_config(tmp_path,cfg),output,plots=False)
    assert result['termination_status']=='INITIALIZATION_INVALID'
    assert result['failure_stage']=='initialization'
    assert not result['success']
    assert {'metrics.json','trajectory.npz','state.json'} <= {p.name for p in output.iterdir()}
    assert (output/'state.json').read_text().find('completed')>=0
    assert 'task_request_sha256' in result and result['input_snapshot_sha256'] is None


def test_jupedsim_capacity_failure_is_not_an_experiment_error(tmp_path):
    cfg=load_config(ROOT/'configs/step1/scenarios/opposite_side.yaml',seed=1)
    result=experiment(write_config(tmp_path,cfg),tmp_path/'crowded',plots=False)
    assert result['termination_status']=='INITIALIZATION_INVALID'
    assert result['failure_stage']=='initialization'
    assert 'could be placed' in result['failure_reason']


def test_stall_runs_all_recovery_stages_then_stops(tmp_path):
    cfg=config(); cfg['guides']['max_speed']=.001; cfg['simulation']['max_steps']=100
    result=experiment(write_config(tmp_path,cfg),tmp_path/'stall',plots=False)
    assert result['termination_status']=='REPLAN_EXHAUSTED'
    assert result['replan_count']==3
    assert [event['strategy'] for event in result['deadlock_events']] == [
        'path_recompute','reachable_reassignment','priority_yield','exhausted']
    assert result['criteria']['safety_ok']


def test_fixed_n_resume_hash_and_saved_trajectory_reevaluation(tmp_path):
    output=tmp_path/'fixed'
    first=experiment(ROOT/'configs/step1/square.yaml',output,plots=False,
                     protocol='fixed_n',fixed_n=20,method='equal_arc')
    assert first['success'] and first['active_guides']==20
    resumed=experiment(ROOT/'configs/step1/square.yaml',output,plots=False,
                       protocol='fixed_n',fixed_n=20,method='equal_arc',resume=True)
    assert resumed['task_sha256']==first['task_sha256']
    reevaluated=reevaluate_result(output)
    assert reevaluated['success']==first['success']
    with pytest.raises(FileExistsError,match='hash-mismatched'):
        experiment(ROOT/'configs/step1/square.yaml',output,seed=1,plots=False,
                   protocol='fixed_n',fixed_n=20,method='equal_arc',resume=True)

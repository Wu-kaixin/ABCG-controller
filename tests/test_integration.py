"""Integration checks for this migration, beyond the upstream equation tests."""
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon
import yaml

from controller import PeriodicArcCVTConfig, VelocitySafetyConfig
from controller.boundary import BoundaryEstimateV2, boundary_v2_from_curve, build_deployment_boundary
from controller.coverage import boundary_demand, plan_weighted_arc_coverage
from environment import build_environment, sample_attributes
from run import load_config, run_experiment, swept_safety

ROOT = Path(__file__).resolve().parents[1]
SQUARE = ROOT / 'configs/step1/square.yaml'


def test_jupedsim_snapshot_is_reproducible_static_and_isolated():
    cfg = load_config(SQUARE)
    first, second = build_environment(cfg), build_environment(cfg)
    cloud = first.observe()
    np.testing.assert_array_equal(cloud, second.observe())
    first.advance(.1)
    np.testing.assert_array_equal(cloud, first.observe())
    cloud[:] = 0
    assert np.any(first.observe() != 0)
    assert not first._positions.flags.writeable
    observation = first.observe_agent(0, np.array([[1., 1.], [2., 1.]]), 0)
    assert 'spawn_vertices' not in asdict(observation)
    assert observation.neighbor_guide_ids == (1,)
    assert np.ptp(first.attributes['radius']) > 0


def test_jupedsim_initial_spacing_respects_heterogeneous_radii():
    env = build_environment(load_config(SQUARE))
    points, radii = env.observe(), env.attributes['radius']
    distances = np.linalg.norm(points[:, None]-points[None], axis=2)
    np.fill_diagonal(distances, np.inf)
    assert np.all(distances >= radii[:, None]+radii[None])


def test_invalid_attribute_distribution_is_rejected():
    with pytest.raises(ValueError):
        sample_attributes(10, {'radius': {'std': float('nan')}}, 0)
    with pytest.raises(ValueError):
        sample_attributes(10, {'demand_weight': {'min': 0}}, 0)


def test_deployment_uses_its_own_perimeter():
    angles = np.linspace(0, 2*np.pi, 160, endpoint=False)
    curve = [5., 5.] + 2*np.column_stack((np.cos(angles), np.sin(angles)))
    estimate = boundary_v2_from_curve(curve, 0, .05, 'test')
    deployment = build_deployment_boundary(estimate, 1., .05, (10., 10.), .2)
    assert isinstance(deployment, BoundaryEstimateV2)
    assert deployment.length == pytest.approx(Polygon(estimate.curve_points).buffer(1., quad_segs=16).length, rel=.002)
    assert deployment.length > estimate.length + 6
    assert deployment.diagnostics['length_semantics'] == 'deployment_curve'


def test_demand_changes_weighted_plan_and_cost_never_increases():
    angles = np.linspace(0, 2*np.pi, 200, endpoint=False)
    curve = 3*np.column_stack((np.cos(angles), np.sin(angles)))
    boundary = boundary_v2_from_curve(curve, 0, .07, 'test')
    points = np.array([[-2., 0.], [2., 0.]])
    uniform = boundary_demand(boundary, points, np.ones(2), .8)
    weighted = boundary_demand(boundary, points, np.array([.7, 1.3]), .8)
    cfg = PeriodicArcCVTConfig(max_iterations=500, h_tolerance=1e-8)
    a = plan_weighted_arc_coverage(boundary, 12, uniform, cfg)
    b = plan_weighted_arc_coverage(boundary, 12, weighted, cfg)
    assert a.converged and b.converged
    assert not np.allclose(a.target_s, b.target_s)
    assert np.all(np.diff(b.h_history) <= 1e-10)
    assert np.mean(np.sort(np.diff(np.r_[b.target_s, b.target_s[0]+boundary.length]))) > 0


def test_swept_check_detects_collision_between_safe_endpoints():
    positions = np.array([[[1., 2.], [3., 2.]], [[3., 2.], [1., 2.]]])
    result = swept_safety(positions, np.array([[4., 4.]]), np.array([5., 5.]), VelocitySafetyConfig())
    assert result['min_guide_pair_center_distance'] == pytest.approx(0)
    assert not result['swept_safety_passed']


@pytest.mark.parametrize('scene', ['square', 'rectangle'])
def test_default_scenes_execute_real_jupedsim_and_converge(tmp_path, scene):
    result = run_experiment(ROOT/f'configs/step1/{scene}.yaml', tmp_path/scene, plots=False)
    assert result['deployment_success']
    assert result['control_steps'] > 10
    assert result['tracking_rmse'] < .03
    assert result['swept_safety_passed']
    assert result['crowd_static']
    data = np.load(tmp_path/scene/'trajectory.npz')
    assert len(data['guide_positions']) == len(data['applied_controls'])+1
    assert data['crowd_positions'].shape[1] == 2
    assert data['guide_positions'].shape[1] > result['active_guides']


def write_config(tmp_path, cfg):
    path = tmp_path/'case.yaml'
    path.write_text(yaml.safe_dump(cfg), encoding='utf-8')
    return path


@pytest.mark.parametrize('change', ['open', 'dynamic', 'limited', 'override', 'unknown'])
def test_out_of_scope_or_unknown_options_fail_loudly(tmp_path, change):
    cfg = load_config(SQUARE)
    if change == 'open':
        cfg['scene']['openings'] = [{'wall': 'top', 'start': 1, 'end': 2}]
    elif change == 'dynamic':
        cfg['crowd']['static'] = False
    elif change == 'limited':
        cfg['guides']['communication'] = 'local'
    elif change == 'override':
        cfg['controller']['boundary']['room_size'] = [10, 10]
    else:
        cfg['scene']['obstacles'] = []
    with pytest.raises(ValueError):
        build_environment(load_config(write_config(tmp_path, cfg)))


@pytest.mark.parametrize('case,status', [('capacity', 'CAPACITY_SHORTFALL'), ('boundary', 'BOUNDARY_INVALID'), ('timeout', 'TIMEOUT')])
def test_scientific_failure_has_explicit_status_and_serializable_results(tmp_path, case, status):
    cfg = load_config(SQUARE)
    if case == 'capacity':
        cfg['guides']['count'] = 3
    elif case == 'boundary':
        cfg['controller']['boundary']['alpha_radius'] = .0001
    else:
        cfg['simulation']['max_steps'] = 1
    result = run_experiment(write_config(tmp_path, cfg), tmp_path/'out', plots=False)
    assert result['status'] == status
    assert not result['deployment_success']
    data = json.loads((tmp_path/'out/metrics.json').read_text())
    assert data['status'] == status
    assert (tmp_path/'out/trajectory.npz').exists()


def test_output_is_not_overwritten(tmp_path):
    out = tmp_path/'occupied'
    out.mkdir()
    (out/'old_result').write_text('keep')
    with pytest.raises(FileExistsError):
        run_experiment(SQUARE, out, plots=False)
    assert (out/'old_result').read_text() == 'keep'


def test_runtime_control_period_respects_gain_bound():
    from controller import ABCGController, ABCGv2Config, AssignmentConfig, assign_guides_to_targets
    guides = np.array([[1., 1.], [3., 1.]])
    targets = np.array([[1., 2.], [3., 2.]])
    controller = ABCGController(ABCGv2Config(k_p=1.5))
    controller.reset(targets, assign_guides_to_targets(guides, targets, AssignmentConfig()), guides)
    with pytest.raises(ValueError, match=r'dt \* k_p'):
        controller.step(np.array([[2., 4.]]), guides, 1.0)

"""Run a Step-1 experiment or independent seeds in parallel."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
import os
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point
import yaml

from controller import ABCGController
from controller.safety import Safety, is_safe, path_clearances
from environment import Environment


def load_config(path, seed=None):
    with Path(path).open(encoding='utf-8') as file:
        config = yaml.safe_load(file)
    schema = {
        'scene': {'type', 'width', 'height', 'openings'},
        'crowd': {'count', 'spawn_vertices', 'spacing', 'radius', 'demand'},
        'guides': {'count', 'radius', 'max_speed', 'initial_inset'},
        'controller': {'offset', 'sample_spacing', 'target_gap', 'demand_bandwidth', 'gain', 'tolerance', 'hold_steps', 'clearance'},
        'simulation': {'seed', 'dt', 'max_steps'},
    }
    if not isinstance(config, dict) or set(config) != {'step', *schema} or config['step'] != 1:
        raise ValueError('Only the documented Step-1 configuration is supported')
    for section, fields in schema.items():
        if not isinstance(config[section], dict) or set(config[section]) != fields:
            raise ValueError(f'{section} requires exactly: {sorted(fields)}')
    if seed is not None:
        config['simulation']['seed'] = seed
    integers = [('crowd', 'count', 3), ('guides', 'count', 3), ('simulation', 'seed', 0),
                ('simulation', 'max_steps', 1), ('controller', 'hold_steps', 1)]
    for section, field, minimum in integers:
        value = config[section][field]
        if type(value) is not int or value < minimum:
            raise ValueError(f'{section}.{field} must be an integer >= {minimum}')
    for section, fields in {
        'scene': ['width', 'height'], 'crowd': ['spacing'],
        'guides': ['radius', 'max_speed', 'initial_inset'],
        'controller': ['offset', 'sample_spacing', 'target_gap', 'demand_bandwidth', 'gain', 'tolerance', 'clearance'],
        'simulation': ['dt'],
    }.items():
        for field in fields:
            value = config[section][field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0:
                raise ValueError(f'{section}.{field} must be finite and positive')
    for name in ['radius', 'demand']:
        if set(config['crowd'][name]) != {'mean', 'std', 'min', 'max'}:
            raise ValueError(f'crowd.{name} requires mean, std, min and max')
    if config['simulation']['dt']*config['controller']['gain'] > 1:
        raise ValueError('dt * gain must not exceed 1')
    return config


def experiment(config_path, output, seed=None, plots=True):
    config = load_config(config_path, seed)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Use an empty output directory: {output}')
    env = Environment(config)
    observation = env.observe()
    initial = env.initialize_guides(config['guides'])
    ctrl, sim, guide = config['controller'], config['simulation'], config['guides']
    safety = Safety(2*guide['radius']+ctrl['clearance'],
                    guide['radius']+float(observation.radii.max())+ctrl['clearance'],
                    guide['radius']+ctrl['clearance'], guide['max_speed'])
    controller = ABCGController(ctrl, safety, env.scene.size)
    positions, velocities = [initial], []
    minima = path_clearances(initial, initial, observation.positions, env.scene.size)
    status, reason, hold = 'TIMEOUT', '', 0
    try:
        if not is_safe(minima, safety):
            raise ValueError('INITIALIZATION_INVALID: guides violate safety distances')
        controller.prepare(observation, initial)
        for _ in range(sim['max_steps']):
            current = positions[-1]
            velocity = controller.step(env.observe(), current, sim['dt'])
            next_position = current+sim['dt']*velocity
            clearance = path_clearances(current, next_position, observation.positions, env.scene.size)
            if not is_safe(clearance, safety):
                raise ValueError('SAFETY_INFEASIBLE: execution path failed the distance check')
            minima = {key: min(minima[key], clearance[key]) for key in minima}
            positions.append(next_position)
            velocities.append(velocity)
            env.advance(sim['dt'])
            settled = controller.tracking_error(next_position) <= ctrl['tolerance'] and np.linalg.norm(velocity, axis=1).max() <= ctrl['tolerance']
            hold = hold+1 if settled else 0
            if hold >= ctrl['hold_steps']:
                status = 'CONVERGED'
                break
    except ValueError as error:
        reason = str(error)
        known = {'BOUNDARY_INVALID', 'OFFSET_INVALID', 'CAPACITY_SHORTFALL', 'PLAN_INVALID',
                 'PLAN_TIMEOUT', 'SAFETY_INFEASIBLE', 'INITIALIZATION_INVALID'}
        status = reason.split(':')[0]
        if status not in known:
            raise
    trajectory = np.asarray(positions)
    active = controller.assignment >= 0 if controller.assignment is not None else np.zeros(len(initial), dtype=bool)
    tracking_error = controller.tracking_error(positions[-1]) if active.any() else None
    max_gap = None
    if active.any():
        line = LineString(np.vstack([controller.boundary.deployment, controller.boundary.deployment[0]]))
        arcs = np.sort([line.project(Point(p)) for p in positions[-1][active]])
        max_gap = float(np.diff(np.r_[arcs, arcs[0]+line.length]).max())
    metrics = {
        'status': status, 'reason': reason, 'seed': sim['seed'], 'scene': env.scene.name,
        'success': status == 'CONVERGED' and is_safe(minima, safety),
        'steps': len(velocities), 'time': len(velocities)*sim['dt'],
        'active_guides': int(active.sum()), 'reserve_guides': int(len(initial)-active.sum()),
        'tracking_rmse': tracking_error, 'max_arc_gap': max_gap,
        'minimum_distances': minima, 'safety_limits': asdict(safety),
        'crowd_static': bool(np.array_equal(observation.positions, env.observe().positions)),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output/'metrics.json').write_text(json.dumps(metrics, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    (output/'config.yaml').write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
    np.savez_compressed(output/'trajectory.npz', guide_positions=trajectory,
        velocities=np.asarray(velocities).reshape(-1, len(initial), 2), crowd_positions=observation.positions,
        crowd_radii=observation.radii, crowd_demand=observation.demand,
        targets=controller.plan.positions if controller.plan is not None else np.empty((0, 2)),
        assignment=controller.assignment if controller.assignment is not None else np.full(len(initial), -1),
        times=np.arange(len(positions))*sim['dt'])
    if plots:
        from visualization import plot_result
        plot_result(env, trajectory, controller, metrics, output/'scene.png')
    return metrics


def _worker(arguments):
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        return experiment(*arguments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--seed', type=int)
    choice.add_argument('--seeds', type=int, nargs='+')
    parser.add_argument('--workers', default='auto')
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args()
    if args.seeds is None:
        result = experiment(args.config, args.output, args.seed, not args.no_plots)
        print(json.dumps(result, indent=2))
        return
    if min(args.seeds) < 0 or len(args.seeds) != len(set(args.seeds)):
        parser.error('Seeds must be distinct nonnegative integers')
    output = Path(args.output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Use an empty output directory: {output}')
    available = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count() or 1
    workers = min(available if args.workers == 'auto' else int(args.workers), len(args.seeds))
    if workers < 1:
        parser.error('workers must be positive')
    tasks = [(args.config, output/f'seed_{seed}', seed, not args.no_plots) for seed in args.seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_worker, tasks))
    summary = {'runs': len(results), 'successful': sum(r['success'] for r in results), 'workers': workers, 'results': results}
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(f"{summary['successful']}/{summary['runs']} successful; {workers} worker processes")


if __name__ == '__main__':
    main()

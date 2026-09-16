"""One entry point: YAML -> JuPedSim snapshot -> ABCG -> auditable results."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess

import numpy as np
from shapely.geometry import LineString, Point, Polygon
import yaml

from controller import (
    ABCGController, ABCGv2Config, AssignmentConfig, PeriodicArcCVTConfig,
    ResourcePolicy, ResourcePolicyConfig, VelocitySafetyConfig,
    assign_guides_to_targets, integrate_guide_positions, plan_periodic_arc_coverage,
)
from controller.boundary import (
    BoundaryEstimateFailure, BoundaryV2Config, build_deployment_boundary, estimate_boundary_v2,
)
from controller.coverage import boundary_demand, plan_weighted_arc_coverage
from environment import build_environment, initialize_guides, integer, positive


def load_config(path: str | Path, seed: int | None = None) -> dict:
    with Path(path).open(encoding="utf-8") as stream:
        cfg = yaml.safe_load(stream)
    required = {"step", "scene", "crowd", "guides", "controller", "simulation"}
    if not isinstance(cfg, dict) or set(cfg) != required:
        raise ValueError(f"Configuration requires exactly these groups: {sorted(required)}")
    sim = cfg["simulation"]
    if set(sim) != {"seed", "dt", "max_steps"}:
        raise ValueError("simulation requires seed, dt and max_steps")
    if seed is not None:
        sim["seed"] = integer(seed, "seed", 0)
    integer(sim["seed"], "seed", 0)
    integer(sim["max_steps"], "max_steps")
    positive(sim["dt"], "dt")
    guides = cfg["guides"]
    if set(guides) != {"count", "radius", "max_speed", "sensing", "communication", "initialization"}:
        raise ValueError("Unknown or missing guide parameter")
    if guides["sensing"] != "global" or guides["communication"] != "unlimited":
        raise ValueError("Step 1 currently requires global sensing and unlimited communication")
    integer(guides["count"], "guides.count")
    positive(guides["radius"], "guides.radius")
    positive(guides["max_speed"], "guides.max_speed")
    control = cfg["controller"]
    if set(control) != {"boundary", "deployment", "resources", "planning", "assignment", "motion", "safety"}:
        raise ValueError("Unknown or missing controller section")
    deployment = control["deployment"]
    if set(deployment) != {"offset", "sample_spacing", "weighted", "demand_bandwidth"}:
        raise ValueError("Unknown or missing deployment setting")
    if not isinstance(deployment["weighted"], bool):
        raise ValueError("deployment.weighted must be boolean")
    for name in ("offset", "sample_spacing", "demand_bandwidth"):
        positive(deployment[name], name)
    safety = control["safety"]
    if set(safety) != {"crowd_clearance", "guide_clearance", "wall_clearance", "residual_tolerance", "max_projection_sweeps"}:
        raise ValueError("Unknown or missing safety setting")
    for name in ("crowd_clearance", "guide_clearance", "wall_clearance"):
        positive(safety[name], name, zero=True)
    # Derived fields have one owner; YAML cannot silently override them.
    for name, forbidden in {
        "boundary": {"safety_distance", "room_size", "room_margin"},
        "motion": {"dt", "v_max", "max_steps"},
    }.items():
        if set(control[name]) & forbidden:
            raise ValueError(f"{name}: derived fields cannot be set: {forbidden}")
    return cfg


def make_safety(cfg: dict, attributes: dict) -> VelocitySafetyConfig:
    raw = cfg["controller"]["safety"]
    radius = float(cfg["guides"]["radius"])
    # Conservative maximum radius keeps the migrated scalar safety filter small.
    return VelocitySafetyConfig(
        min_crowd_distance=radius + float(np.max(attributes["radius"])) + raw["crowd_clearance"],
        min_guide_distance=2*radius + raw["guide_clearance"],
        room_margin=radius + raw["wall_clearance"],
        residual_tolerance=raw["residual_tolerance"],
        max_projection_sweeps=raw["max_projection_sweeps"],
    )


def swept_safety(positions: np.ndarray, crowd: np.ndarray, room: np.ndarray,
                 safety: VelocitySafetyConfig) -> dict:
    """Exact minimum distances on piecewise-linear executed guide segments.

    This checks the simulated constant-velocity plant, not robot tracking errors.
    """
    start, end = (positions[:-1], positions[1:]) if len(positions) > 1 else (positions, positions)
    delta = end - start

    def segment_min(rel, motion):
        denom = np.sum(motion**2, axis=-1)
        alpha = np.clip(-np.sum(rel*motion, axis=-1)/np.maximum(denom, 1e-30), 0, 1)
        return float(np.linalg.norm(rel + alpha[..., None]*motion, axis=-1).min())

    crowd_distance = segment_min(start[:, :, None] - crowd[None, None], delta[:, :, None])
    first, second = np.triu_indices(positions.shape[1], 1)
    guide_distance = None if not len(first) else segment_min(start[:, first] - start[:, second], delta[:, first] - delta[:, second])
    wall_distance = float(np.minimum(positions, room - positions).min())
    tolerance = 1e-7
    safe = crowd_distance >= safety.min_crowd_distance-tolerance and wall_distance >= safety.room_margin-tolerance
    safe = safe and (guide_distance is None or guide_distance >= safety.min_guide_distance-tolerance)
    return {"min_guide_crowd_center_distance": crowd_distance,
            "min_guide_pair_center_distance": guide_distance, "min_wall_center_distance": wall_distance,
            "swept_safety_passed": bool(safe), "safety_evaluation": "piecewise_linear_execution"}


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False, default=_json_default)+"\n", encoding="utf-8")


def run_experiment(config_path: str | Path, output: str | Path, seed: int | None = None,
                   plots: bool = True) -> dict:
    cfg = load_config(config_path, seed)
    env = build_environment(cfg)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output}; use a new output path")
    sim, raw = cfg["simulation"], cfg["controller"]
    safety = make_safety(cfg, env.attributes)
    motion = ABCGv2Config(dt=sim["dt"], max_steps=sim["max_steps"], v_max=cfg["guides"]["max_speed"], **raw["motion"])
    boundary_cfg = BoundaryV2Config(safety_distance=0.0, **raw["boundary"])
    planner_cfg = PeriodicArcCVTConfig(**raw["planning"])
    assignment_cfg = AssignmentConfig(**raw["assignment"])
    resource_policy = ResourcePolicy(ResourcePolicyConfig(**raw["resources"]))
    cloud = env.observe()
    room = np.array([env.scenario.width, env.scenario.height])
    guides = initialize_guides(cfg, env, safety.min_crowd_distance, safety.min_guide_distance, safety.room_margin)
    positions, controls, nominal, records = [guides.copy()], [], [], []
    estimate = estimate_boundary_v2(cloud, boundary_cfg, np.random.default_rng(sim["seed"]))
    deployment = plan = resource = assignment = None
    status = "INIT"
    details = {}
    if isinstance(estimate, BoundaryEstimateFailure):
        status, details = estimate.status, estimate.diagnostics
    else:
        deployment = build_deployment_boundary(estimate, raw["deployment"]["offset"],
            raw["deployment"]["sample_spacing"], tuple(room), safety.room_margin)
        if isinstance(deployment, BoundaryEstimateFailure):
            status, details = deployment.status, deployment.diagnostics
        else:
            line = LineString(np.vstack((deployment.offset_points, deployment.offset_points[0])))
            clearance = min(line.distance(Point(p)) for p in cloud)
            envelope = Polygon(deployment.offset_points)
            if not all(envelope.covers(Point(p)) for p in cloud):
                status, details = "OFFSET_INVALID", {"reason": "deployment_does_not_enclose_observed_crowd"}
            elif clearance < safety.min_crowd_distance - 1e-7:
                status, details = "OFFSET_INVALID", {"reason": "deployment_curve_too_close_to_observed_crowd", "minimum_clearance": clearance}
            else:
                resource = resource_policy.decide(deployment.length, len(guides))
                if resource.status != "VALID":
                    status, details = resource.status, asdict(resource)
                else:
                    if raw["deployment"]["weighted"]:
                        density = boundary_demand(deployment, cloud, env.attributes["demand_weight"], raw["deployment"]["demand_bandwidth"])
                        plan = plan_weighted_arc_coverage(deployment, resource.active_count, density, planner_cfg)
                    else:
                        plan = plan_periodic_arc_coverage(deployment, resource.active_count, planner_cfg)
                    if not plan.converged or plan.status != "VALID":
                        status, details = plan.status, plan.diagnostics
                    else:
                        distances = np.linalg.norm(plan.target_xy[:, None] - plan.target_xy[None, :], axis=2)
                        np.fill_diagonal(distances, np.inf)
                        if distances.min() < safety.min_guide_distance:
                            status, details = "ASSIGNMENT_INFEASIBLE", {"reason": "planned_targets_violate_guide_clearance"}
                        else:
                            assignment = assign_guides_to_targets(guides, plan.target_xy, assignment_cfg)
                            if assignment.status != "VALID":
                                status, details = assignment.status, assignment.diagnostics
                            else:
                                controller = ABCGController(motion, safety)
                                controller.reset(plan.target_xy, assignment, guides, room)
                                for step in range(sim["max_steps"]):
                                    command = controller.step(env.observe(), guides, sim["dt"])
                                    nominal.append(command.preferred_velocity.copy())
                                    controls.append(command.safe_velocity.copy())
                                    guides = integrate_guide_positions(guides, command.safe_velocity, sim["dt"])
                                    env.advance(sim["dt"])
                                    positions.append(guides.copy())
                                    records.append({"time": (step+1)*sim["dt"], "state": command.state,
                                                    "tracking_rmse_before_step": command.diagnostics["tracking_rmse"],
                                                    "safety_status": command.diagnostics["safety_status"],
                                                    "safety_residual": command.diagnostics.get("safety_max_residual_after", 0.0)})
                                    status = command.state
                                    if status not in {"INIT", "TRACK", "HOLD"}:
                                        break
    trajectory = np.asarray(positions)
    metrics = {"schema_version": 1, "step": 1, "seed": sim["seed"], "scene": env.scenario.name,
               "status": status, "converged": status == "CONVERGED", "diagnostics": details,
               "control_steps": len(controls), "elapsed_simulation_time": len(controls)*sim["dt"],
               "crowd_static": bool(np.array_equal(cloud, env.observe())),
               "crowd_count": len(cloud), "available_guides": len(guides),
               "active_guides": resource.active_count if resource else 0,
               "estimated_boundary_valid": not isinstance(estimate, BoundaryEstimateFailure),
               "deployment_valid": deployment is not None and not isinstance(deployment, BoundaryEstimateFailure) and status != "OFFSET_INVALID",
               "planning_status": plan.status if plan else "NOT_RUN",
               "resource_status": resource.status if resource else "NOT_RUN",
               "assignment_status": assignment.status if assignment else "NOT_RUN",
               "tracking_rmse": None, "max_arc_gap_final": None,
               "max_arc_gap_planned": plan.max_arc_gap if plan else None,
               "estimated_crowd_perimeter": estimate.length if not isinstance(estimate, BoundaryEstimateFailure) else None,
               "deployment_perimeter": deployment.length if deployment is not None and not isinstance(deployment, BoundaryEstimateFailure) else None,
               "safety_thresholds": asdict(safety),
               **swept_safety(trajectory, cloud, room, safety)}
    if assignment is not None and plan is not None and assignment.status == "VALID":
        active = assignment.guide_to_target >= 0
        errors = guides[active] - plan.target_xy[assignment.guide_to_target[active]]
        metrics["tracking_rmse"] = float(np.sqrt(np.mean(np.sum(errors**2, axis=1))))
        line = LineString(np.vstack((deployment.offset_points, deployment.offset_points[0])))
        arcs = np.sort([line.project(Point(p)) for p in guides[active]])
        metrics["max_arc_gap_final"] = float(np.max(np.diff(np.r_[arcs, arcs[0]+line.length])))
    metrics["max_executed_speed"] = float(np.linalg.norm(np.asarray(controls), axis=-1).max()) if controls else 0.0
    metrics["deployment_success"] = bool(metrics["converged"] and metrics["swept_safety_passed"] and metrics["crowd_static"] and metrics["tracking_rmse"] is not None and metrics["tracking_rmse"] <= motion.tracking_rmse_tolerance)
    write_json(output / "metrics.json", metrics)
    write_json(output / "trace.json", records)
    write_json(output / "resolved_config.json", cfg)
    for name, value in (("boundary", estimate), ("deployment", deployment), ("plan", plan), ("resources", resource), ("assignment", assignment)):
        if value is not None:
            write_json(output / f"{name}.json", asdict(value))
    np.savez_compressed(output / "trajectory.npz", times=np.arange(len(positions))*sim["dt"],
        guide_positions=trajectory, applied_controls=np.asarray(controls).reshape(-1, len(guides), 2),
        nominal_controls=np.asarray(nominal).reshape(-1, len(guides), 2), crowd_positions=cloud,
        target_positions=plan.target_xy if plan else np.empty((0, 2)), **env.attributes)
    root = Path(__file__).resolve().parent
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
    code_files = [*root.glob("*.py"), *root.glob("controller/*.py")]
    write_json(output / "manifest.json", {"created_utc": datetime.now(timezone.utc).isoformat(),
        "git_revision": revision, "python": platform.python_version(),
        "packages": {n: version(n) for n in ("numpy", "scipy", "shapely", "jupedsim")},
        "file_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(code_files)},
        "config_sha256": hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
        "resolved_config_sha256": hashlib.sha256((output / "resolved_config.json").read_bytes()).hexdigest(),
        "model": "JuPedSim static snapshot; external velocity-controlled guides",
        "truth_geometry_exposed_to_controller": False})
    if plots:
        from visualization import plot_result
        plot_result(env, trajectory, estimate, deployment, plan, output / "deployment.png", metrics)
    return metrics


def _batch_task(args):
    # Independent seeds run in separate processes; limit nested numerical threads.
    try:
        from threadpoolctl import threadpool_limits
    except ImportError:
        return run_experiment(*args)
    with threadpool_limits(limits=1):
        return run_experiment(*args)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--workers", default="auto", help="processes for independent seeds; auto uses available CPUs")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()
    if args.seed is not None and args.seeds is not None:
        parser.error("Use --seed or --seeds, not both")
    if args.seeds is None:
        result = run_experiment(args.config, args.output, args.seed, not args.no_plots)
        print(json.dumps({k: result[k] for k in ("seed", "status", "deployment_success", "tracking_rmse")}, indent=2))
    else:
        if len(set(args.seeds)) != len(args.seeds) or min(args.seeds) < 0:
            parser.error("Seeds must be unique nonnegative integers")
        batch_root = Path(args.output)
        batch_root.mkdir(parents=True, exist_ok=True)
        if any(batch_root.iterdir()):
            raise FileExistsError(f"Batch output directory is not empty: {batch_root}")
        available = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
        workers = min(available, len(args.seeds)) if args.workers == "auto" else int(args.workers)
        if workers < 1:
            parser.error("workers must be positive")
        workers = min(workers, len(args.seeds))
        tasks = [(args.config, str(Path(args.output)/f"seed_{s}"), s, not args.no_plots) for s in args.seeds]
        if workers == 1:
            results = [_batch_task(t) for t in tasks]
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_batch_task, tasks))
        summary = {"runs": len(results), "workers": workers,
                   "successful": sum(r["deployment_success"] for r in results),
                   "results": results}
        write_json(Path(args.output) / "batch_summary.json", summary)
        print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    # Scientific failures are retained as results; invalid configuration raises.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

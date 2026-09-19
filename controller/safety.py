"""Velocity projection and independent checks of the executed straight segments."""
from dataclasses import dataclass
from time import perf_counter

import numpy as np


@dataclass(frozen=True)
class Safety:
    guide_distance: float
    crowd_distance: float
    wall_distance: float
    max_speed: float
    numeric_tolerance: float = 1e-7


@dataclass(frozen=True)
class SafetyResult:
    velocity: np.ndarray
    status: str
    residual: float
    iterations: int
    correction_norm: float
    min_predicted_clearance: float
    solve_time: float
    fallback_used: bool


def path_clearances(start, end, people, room):
    """Exact closest approach on a constant-velocity execution interval."""
    def closest(relative, motion):
        denominator = np.sum(motion**2, axis=-1)
        t = np.clip(-np.sum(relative*motion, axis=-1)/np.maximum(denominator, 1e-30), 0, 1)
        return float(np.linalg.norm(relative+t[..., None]*motion, axis=-1).min())

    motion = end-start
    crowd = closest(start[:, None]-people[None, :], motion[:, None])
    i, j = np.triu_indices(len(start), 1)
    pair = closest(start[i]-start[j], motion[i]-motion[j]) if len(i) else None
    wall = float(np.minimum(np.stack([start, end]), np.asarray(room)-np.stack([start, end])).min())
    return {'crowd': crowd, 'guides': pair, 'walls': wall}


def is_safe(clearances, limits):
    tol = limits.numeric_tolerance
    return (clearances['crowd'] >= limits.crowd_distance-tol
            and clearances['walls'] >= limits.wall_distance-tol
            and (clearances['guides'] is None or clearances['guides'] >= limits.guide_distance-tol))


def safe_velocity(positions, nominal, people, room, dt, limits):
    """Project onto separation half-spaces and per-guide speed balls.

    The filter is a numerical feasibility method. If convergence is not reached,
    the caller stops the episode explicitly. Initial safety is checked separately.
    """
    started = perf_counter(); n = len(positions)
    initial = path_clearances(positions, positions, people, room)
    if not is_safe(initial, limits):
        raise ValueError('INITIALIZATION_INVALID: current state violates safety distances')
    rows, bounds = [], []

    def add(i, normal, bound, j=None):
        row = np.zeros((n, 2))
        row[i] = normal
        if j is not None:
            row[j] = -normal
        rows.append(row.ravel())
        bounds.append(bound)

    for i in range(n):
        for j in range(i):
            delta = positions[i]-positions[j]
            distance = np.linalg.norm(delta)
            if distance < 1e-12:
                raise ValueError('SAFETY_INFEASIBLE: coincident guides')
            bound = (limits.guide_distance+1e-8-distance)/dt
            if bound > -2*limits.max_speed:
                add(i, delta/distance, bound, j)
        deltas = positions[i]-people
        distances = np.linalg.norm(deltas, axis=1)
        for delta, distance in zip(deltas, distances):
            if distance < 1e-12:
                raise ValueError('SAFETY_INFEASIBLE: guide coincides with a pedestrian')
            bound = (limits.crowd_distance+1e-8-distance)/dt
            if bound > -limits.max_speed:
                add(i, delta/distance, bound)
        for axis in range(2):
            normal = np.eye(2)[axis]
            for direction, gap in [(normal, positions[i, axis]), (-normal, room[axis]-positions[i, axis])]:
                bound = (limits.wall_distance+1e-8-gap)/dt
                if bound > -limits.max_speed:
                    add(i, direction, bound)

    matrix = np.asarray(rows).reshape(-1, 2*n)
    bounds = np.asarray(bounds)
    vector = nominal.ravel().copy()
    corrections = np.zeros((len(rows)+n, 2*n))
    for iteration in range(1, 201):
        for k, (row, bound) in enumerate(zip(matrix, bounds)):
            shifted = vector+corrections[k]
            projected = shifted + max(0., bound-row@shifted)/(row@row)*row
            corrections[k] = shifted-projected
            vector = projected
        for i in range(n):
            k = len(rows)+i
            shifted = vector+corrections[k]
            projected = shifted.copy()
            block = projected[2*i:2*i+2]
            block *= min(1., limits.max_speed/max(np.linalg.norm(block), 1e-30))
            corrections[k] = shifted-projected
            vector = projected
        residual = np.max(bounds-matrix@vector, initial=0.)
        if residual <= 1e-9:
            velocity = vector.reshape(n, 2)
            checked = path_clearances(positions, positions+dt*velocity, people, room)
            if is_safe(checked, limits):
                return SafetyResult(velocity, 'SOLVED', float(residual), iteration,
                    float(np.linalg.norm(velocity-nominal)), float(min(v for v in checked.values() if v is not None)),
                    perf_counter()-started, False)
    # A stopped single-integrator is safe whenever the current state is safe.
    stopped = np.zeros_like(nominal); checked = path_clearances(positions, positions, people, room)
    if is_safe(checked, limits):
        return SafetyResult(stopped, 'NUMERICAL_FALLBACK', float(np.max(bounds-matrix@vector, initial=0.)),
            200, float(np.linalg.norm(nominal)), float(min(v for v in checked.values() if v is not None)),
            perf_counter()-started, True)
    raise ValueError('NUMERICAL_FAILURE: projection failed and stopped fallback is unsafe')

"""Deterministic planners on a sampled periodic deployment curve."""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Plan:
    positions: np.ndarray
    arc_positions: np.ndarray
    cost: np.ndarray
    max_gap: float
    method: str
    iterations: int
    exit_reason: str
    density_total: float


def _density(points, people, demand, bandwidth, mode):
    squared = np.sum((points[:, None]-people[None, :])**2, axis=2)
    shifted = squared-squared.min(axis=1, keepdims=True)
    kernel = np.exp(-shifted/(2*bandwidth**2))
    mass = kernel @ demand
    if mode == 'average_cvt':
        return mass/np.maximum(kernel.sum(axis=1), np.finfo(float).tiny)
    return mass


def _interpolate(boundary, sites):
    return np.column_stack([np.interp(sites, np.r_[boundary.arc, boundary.length],
        np.r_[boundary.deployment[:, d], boundary.deployment[0, d]]) for d in range(2)])


def plan_coverage(boundary, people, demand, count, bandwidth, method='average_cvt',
                  phase=0., samples=2048, max_iterations=300):
    """Plan sites; each fixed-N history belongs to one deterministic attempt."""
    if count < 3:
        raise ValueError('At least three targets are required')
    if not np.isfinite(bandwidth) or bandwidth <= 0:
        raise ValueError('Demand bandwidth must be positive')
    demand = np.asarray(demand, dtype=float)
    if demand.shape != (len(people),) or not np.isfinite(demand).all() or np.any(demand <= 0):
        raise ValueError('Demand must be finite, positive and match the people')
    if method not in {'equal_arc', 'average_cvt', 'mass_cvt', 'distmesh'}:
        raise ValueError(f'Unknown planning method: {method}')
    points, length = boundary.deployment, boundary.length
    density = np.ones(len(points)) if method == 'equal_arc' else _density(
        points, np.asarray(people), demand, bandwidth,
        'average_cvt' if method == 'average_cvt' else 'mass_cvt')
    arc = boundary.arc
    quadrature = (np.arange(samples)+0.5)*length/samples
    rho = np.interp(quadrature, np.r_[arc, length], np.r_[density, density[0]])
    mass = rho*length/samples
    sites = (np.arange(count)+phase)*length/count % length

    def cells(current):
        delta = (quadrature[:, None]-current[None, :]+length/2) % length-length/2
        owner = np.argmin(np.abs(delta), axis=1)
        nearest = delta[np.arange(len(delta)), owner]
        return owner, nearest, float(np.sum(mass*nearest**2))

    owner, delta, cost = cells(sites)
    history = [cost]
    if method == 'equal_arc':
        targets = _interpolate(boundary, np.sort(sites))
        return Plan(targets, np.sort(sites), np.array(history), length/count,
                    method, 0, 'DIRECT', float(mass.sum()))
    exit_reason = 'ITERATION_LIMIT'
    for iteration in range(1, max_iterations+1):
        totals = np.bincount(owner, weights=mass, minlength=count)
        if np.any(totals <= 0):
            raise ValueError('PLAN_INVALID: empty coverage cell')
        if method == 'distmesh':
            # A periodic spacing relaxation: equalise integral of sqrt(rho).
            cumulative = np.cumsum(np.sqrt(np.maximum(mass, np.finfo(float).tiny)))
            desired = np.interp((np.arange(count)+.5)*cumulative[-1]/count,
                                cumulative, quadrature)
            move = ((desired-sites+length/2) % length)-length/2
            move *= .35
        else:
            move = np.bincount(owner, weights=mass*delta, minlength=count)/totals
        sites = np.sort((sites+move) % length)
        owner, delta, next_cost = cells(sites)
        if method != 'distmesh' and next_cost > cost+1e-9:
            raise ValueError('PLAN_INVALID: coverage cost increased')
        history.append(next_cost)
        if np.max(np.abs(move)) < 1e-5 or cost-next_cost <= 1e-8*max(1., cost):
            exit_reason = 'CONVERGED'
            break
        cost = next_cost
    targets = _interpolate(boundary, sites)
    return Plan(targets, sites, np.array(history),
                float(np.diff(np.r_[sites, sites[0]+length]).max()), method,
                len(history)-1, exit_reason, float(mass.sum()))

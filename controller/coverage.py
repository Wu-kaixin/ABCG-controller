"""Demand-weighted periodic arc-length Lloyd planning (discrete CVT)."""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Plan:
    positions: np.ndarray
    arc_positions: np.ndarray
    cost: np.ndarray
    max_gap: float


def plan_coverage(boundary, people, demand, count, bandwidth):
    """Plan target sites on one closed curve; confidence is not a demand weight."""
    if count < 3:
        raise ValueError('At least three targets are required')
    if not np.isfinite(bandwidth) or bandwidth <= 0:
        raise ValueError('Demand bandwidth must be positive')
    demand = np.asarray(demand, dtype=float)
    if demand.shape != (len(people),) or not np.isfinite(demand).all() or np.any(demand <= 0):
        raise ValueError('Demand must be finite, positive and match the people')
    points, length = boundary.deployment, boundary.length
    squared = np.sum((points[:, None]-people[None, :])**2, axis=2)
    kernel = np.exp(-(squared-squared.min(axis=1, keepdims=True))/(2*bandwidth**2))
    density = (kernel @ demand) / kernel.sum(axis=1)
    arc = boundary.arc
    quadrature = (np.arange(2048)+0.5)*length/2048
    mass = np.interp(quadrature, np.r_[arc, length], np.r_[density, density[0]])*length/2048
    sites = np.arange(count)*length/count

    def cells(current):
        delta = (quadrature[:, None]-current[None, :]+length/2) % length-length/2
        owner = np.argmin(np.abs(delta), axis=1)
        nearest = delta[np.arange(len(delta)), owner]
        return owner, nearest, float(np.sum(mass*nearest**2))

    owner, delta, cost = cells(sites)
    history = [cost]
    for _ in range(300):
        totals = np.bincount(owner, weights=mass, minlength=count)
        if np.any(totals <= 0):
            raise ValueError('PLAN_INVALID: empty coverage cell')
        move = np.bincount(owner, weights=mass*delta, minlength=count)/totals
        sites = np.sort((sites+move) % length)
        owner, delta, next_cost = cells(sites)
        if next_cost > cost+1e-9:
            raise ValueError('PLAN_INVALID: coverage cost increased')
        history.append(next_cost)
        if np.max(np.abs(move)) < 1e-5 or cost-next_cost <= 1e-8*max(1., cost):
            break
        cost = next_cost
    else:
        raise ValueError('PLAN_TIMEOUT: coverage planning did not converge')
    targets = np.column_stack([np.interp(sites, np.r_[arc, length], np.r_[points[:, d], points[0, d]]) for d in range(2)])
    return Plan(targets, sites, np.array(history), float(np.diff(np.r_[sites, sites[0]+length]).max()))

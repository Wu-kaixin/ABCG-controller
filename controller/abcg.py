"""ABCG: estimate, plan, assign, then apply safe velocity feedback."""
import numpy as np
from scipy.optimize import linear_sum_assignment

from .boundary import estimate_boundary
from .coverage import plan_coverage
from .safety import safe_velocity


class ABCGController:
    def __init__(self, config, safety, room):
        self.config = config
        self.safety = safety
        self.room = np.asarray(room, dtype=float)
        self.boundary = self.plan = self.assignment = None

    def prepare(self, observation, guide_positions):
        """Input contains observed positions and attributes, never spawn geometry."""
        cfg = self.config
        self.boundary = estimate_boundary(
            observation.positions, cfg['offset'], cfg['sample_spacing'], self.room,
            self.safety.wall_distance, self.safety.crowd_distance,
        )
        count = max(3, int(np.ceil(self.boundary.length/cfg['target_gap'])))
        if count > len(guide_positions):
            raise ValueError(f'CAPACITY_SHORTFALL: need {count} guides, have {len(guide_positions)}')
        self.plan = plan_coverage(self.boundary, observation.positions, observation.demand,
                                  count, cfg['demand_bandwidth'])
        targets = self.plan.positions
        separation = np.linalg.norm(targets[:, None]-targets[None, :], axis=2)
        np.fill_diagonal(separation, np.inf)
        if separation.min() < self.safety.guide_distance:
            raise ValueError('PLAN_INVALID: target separation is too small')
        cost = np.sum((guide_positions[:, None]-targets[None, :])**2, axis=2)
        guide_ids, target_ids = linear_sum_assignment(cost)
        self.assignment = np.full(len(guide_positions), -1, dtype=int)
        self.assignment[guide_ids] = target_ids

    def tracking_error(self, guide_positions):
        active = self.assignment >= 0
        error = self.plan.positions[self.assignment[active]]-guide_positions[active]
        return float(np.sqrt(np.mean(np.sum(error**2, axis=1))))

    def step(self, observation, guide_positions, dt):
        if self.assignment is None:
            raise RuntimeError('Call prepare() before step()')
        if not np.isfinite(dt) or dt <= 0 or dt*self.config['gain'] > 1:
            raise ValueError('Require 0 < dt * gain <= 1')
        nominal = np.zeros_like(guide_positions)
        active = self.assignment >= 0
        nominal[active] = self.config['gain']*(self.plan.positions[self.assignment[active]]-guide_positions[active])
        speed = np.linalg.norm(nominal, axis=1)
        nominal *= np.minimum(1., self.safety.max_speed/np.maximum(speed, 1e-30))[:, None]
        return safe_velocity(guide_positions, nominal, observation.positions, self.room, dt, self.safety)

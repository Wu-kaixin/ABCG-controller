"""Shared picture of the static crowd and externally integrated guide trajectories."""
from __future__ import annotations

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np

from controller.boundary import BoundaryEstimateFailure


def plot_result(env, trajectory, estimate, deployment, plan, path, metrics):
    fig, ax = plt.subplots(figsize=(9, 6), constrained_layout=True)
    room = env.scenario.boundary_vertices()
    room = np.vstack((room, room[0]))
    ax.plot(*room.T, color='#233142', linewidth=2, label='Closed room')
    points = env.observe()
    scatter = ax.scatter(*points.T, c=env.attributes['demand_weight'], cmap='YlOrRd', s=20, label='Static crowd', zorder=3)
    for point, radius in zip(points, env.attributes['radius']):
        ax.add_patch(Circle(point, radius, color='#d17a48', alpha=.15))
    for value, color, label in ((estimate, '#576b75', 'Estimated crowd boundary'),
                                (deployment, '#1c968f', 'Deployment curve')):
        if value is not None and not isinstance(value, BoundaryEstimateFailure):
            curve = np.vstack((value.offset_points, value.offset_points[0]))
            ax.plot(*curve.T, color=color, linestyle='--', linewidth=1.4, label=label)
    for index in range(trajectory.shape[1]):
        ax.plot(*trajectory[:, index].T, color='#2864bf', alpha=.5, linewidth=.8)
    ax.scatter(*trajectory[0].T, facecolors='none', edgecolors='#2864bf', s=50, label='Initial guides')
    ax.scatter(*trajectory[-1].T, color='#2864bf', marker='^', s=45, label='Final guides', zorder=4)
    if plan is not None:
        ax.scatter(*plan.target_xy.T, marker='+', color='#1c968f', s=90, label='Planned targets', zorder=5)
    fig.colorbar(scatter, ax=ax, label='Individual demand weight', shrink=.6)
    ax.set(aspect='equal', xlabel='x [m]', ylabel='y [m]', title=f"{env.scenario.name} | seed {metrics['seed']} | {metrics['status']}")
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=8)
    ax.grid(alpha=.15)
    fig.savefig(path, dpi=160)
    plt.close(fig)

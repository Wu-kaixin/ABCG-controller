"""Plot the scene, observed crowd, planned boundary and guide trajectories."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np


def plot_result(env, trajectory, controller, metrics, path):
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    ax.plot(*np.asarray(env.scene.polygon.exterior.coords).T, color='#24344d', label='Room')
    crowd = env.observe()
    for point, radius in zip(crowd.positions, crowd.radii):
        ax.add_patch(Circle(point, radius, color='#dc8e55', alpha=.3))
    points = ax.scatter(*crowd.positions.T, c=crowd.demand, cmap='YlOrRd', s=16, label='Static crowd')
    fig.colorbar(points, ax=ax, label='Demand weight', shrink=.6)
    if controller.boundary is not None:
        for curve, label, color in [(controller.boundary.crowd, 'Estimated boundary', '#8b6c56'),
                                    (controller.boundary.deployment, 'Deployment curve', '#159a8c')]:
            ax.plot(*np.vstack([curve, curve[0]]).T, '--', color=color, label=label)
    for i in range(trajectory.shape[1]):
        ax.plot(*trajectory[:, i].T, color='#3778bf', alpha=.4, linewidth=.8)
    ax.scatter(*trajectory[0].T, facecolors='none', edgecolors='#3778bf', label='Initial guides')
    ax.scatter(*trajectory[-1].T, marker='^', color='#3778bf', label='Final guides')
    if controller.plan is not None:
        ax.scatter(*controller.plan.positions.T, marker='+', color='#159a8c', label='Targets')
    ax.set(aspect='equal', xlabel='x [m]', ylabel='y [m]', title=f"{env.scene.name} | {metrics['status']}")
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=8)
    ax.grid(alpha=.15)
    fig.savefig(path, dpi=150)
    plt.close(fig)

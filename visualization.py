"""Plot the scene, observed crowd, planned boundary and guide trajectories."""
import argparse
import json
from pathlib import Path
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
    ax.set(aspect='equal', xlabel='x [m]', ylabel='y [m]', title=f"{env.scene.name} | {metrics['termination_status']}")
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=8)
    ax.grid(alpha=.15)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_saved_result(result_dir, path=None):
    """Regenerate a representative scene solely from persisted evidence."""
    result_dir=Path(result_dir); data=np.load(result_dir/'trajectory.npz',allow_pickle=False)
    metrics=json.loads((result_dir/'metrics.json').read_text(encoding='utf-8'))
    room=data['room']; trajectory=data['positions']
    if room.shape!=(2,) or trajectory.ndim!=3 or not len(trajectory):
        raise ValueError('Saved result has no plottable execution trajectory')
    fig,ax=plt.subplots(figsize=(10,6),constrained_layout=True)
    rectangle=np.array([[0,0],[room[0],0],room,[0,room[1]],[0,0]])
    ax.plot(*rectangle.T,color='#24344d',label='Room')
    points=data['crowd_positions']; radii=data['crowd_radii']; demand=data['crowd_demand']
    for point,radius in zip(points,radii):
        ax.add_patch(Circle(point,radius,color='#dc8e55',alpha=.3))
    scatter=ax.scatter(*points.T,c=demand,cmap='YlOrRd',s=16,label='Static crowd')
    fig.colorbar(scatter,ax=ax,label='Demand weight',shrink=.6)
    for key,label,color in [('boundary_crowd','Estimated boundary','#8b6c56'),
                            ('boundary_deployment','Deployment curve','#159a8c')]:
        curve=data[key]
        if len(curve): ax.plot(*np.vstack([curve,curve[0]]).T,'--',color=color,label=label)
    for guide in range(trajectory.shape[1]):
        ax.plot(*trajectory[:,guide].T,color='#3778bf',alpha=.4,linewidth=.8)
    ax.scatter(*trajectory[0].T,facecolors='none',edgecolors='#3778bf',label='Initial guides')
    ax.scatter(*trajectory[-1].T,marker='^',color='#3778bf',label='Final guides')
    if len(data['targets']):
        ax.scatter(*data['targets'].T,marker='+',color='#159a8c',label='Targets')
    ax.set(aspect='equal',xlabel='x [m]',ylabel='y [m]',
           title=f"{metrics['scene']} | {metrics['method']} | {metrics['termination_status']}")
    ax.legend(loc='upper left',bbox_to_anchor=(1.02,1),fontsize=8); ax.grid(alpha=.15)
    destination=Path(path) if path else result_dir/'scene_from_saved.png'
    fig.savefig(destination,dpi=150); plt.close(fig)
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',required=True); parser.add_argument('--output')
    args=parser.parse_args(); print(plot_saved_result(args.result,args.output))


if __name__=='__main__':
    main()

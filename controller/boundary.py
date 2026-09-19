"""Estimate the crowd envelope and construct an exterior deployment curve."""
from dataclasses import dataclass

import numpy as np
from shapely.geometry import MultiPoint, Point, Polygon
from shapely.geometry.polygon import orient


@dataclass(frozen=True)
class Boundary:
    crowd: np.ndarray
    deployment: np.ndarray
    arc: np.ndarray
    length: float


def estimate_boundary(points, offset, spacing, room, wall_margin, crowd_distance, radii=None):
    """Convex hull is the initial, conservative boundary model.

    Only observed pedestrian positions enter the estimator. The deployment
    buffer is sampled by its own arc length; room geometry is a feasibility check.
    """
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all():
        raise ValueError('BOUNDARY_INVALID: need at least three finite observed points')
    if not np.isfinite(offset) or offset <= 0 or not np.isfinite(spacing) or spacing <= 0:
        raise ValueError('Offset and sample spacing must be positive')
    radii = np.zeros(len(points)) if radii is None else np.asarray(radii, dtype=float)
    if radii.shape != (len(points),) or np.any(radii < 0) or not np.isfinite(radii).all():
        raise ValueError('BOUNDARY_INVALID: radii must be finite and nonnegative')
    # Buffer each observed centre by its physical radius before the conservative
    # convex envelope.  This never reads the generator's spawn polygon.
    occupied = [Point(p).buffer(float(r), quad_segs=32) for p, r in zip(points, radii)]
    hull = MultiPoint(points).convex_hull if not np.any(radii) else Polygon(
        MultiPoint(np.vstack([np.asarray(g.exterior.coords) for g in occupied])).convex_hull.exterior)
    if hull.geom_type != 'Polygon' or hull.area <= 1e-10:
        raise ValueError('BOUNDARY_INVALID: observed positions are degenerate')
    polygon = orient(hull.buffer(offset, quad_segs=32), sign=1)
    line = polygon.exterior
    count = max(32, int(np.ceil(line.length / spacing)))
    deployment = np.array([line.interpolate(i*line.length/count).coords[0] for i in range(count)])
    sampled = Polygon(deployment)
    if np.any(deployment < wall_margin) or np.any(deployment > np.asarray(room)-wall_margin):
        raise ValueError('OFFSET_INVALID: deployment curve exceeds room clearance')
    if not all(sampled.covers(Point(p)) for p in points):
        raise ValueError('OFFSET_INVALID: deployment curve does not enclose the observations')
    if min(sampled.exterior.distance(Point(p)) for p in points) < crowd_distance:
        raise ValueError('OFFSET_INVALID: deployment curve is too close to people')
    lengths = np.linalg.norm(np.roll(deployment, -1, axis=0)-deployment, axis=1)
    arc = np.r_[0., np.cumsum(lengths[:-1])]
    return Boundary(np.asarray(hull.exterior.coords[:-1]), deployment, arc, float(lengths.sum()))

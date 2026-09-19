"""Static visibility-graph navigation and reachable assignment."""
from dataclasses import dataclass
import heapq
import numpy as np
from scipy.optimize import linear_sum_assignment
from shapely.geometry import LineString, Point, Polygon


@dataclass(frozen=True)
class NavigationResult:
    assignment: np.ndarray
    paths: tuple
    lengths: np.ndarray
    reachable: np.ndarray


def _shortest(start, target, free, obstacle):
    direct = LineString([start, target])
    if free.covers(direct) and (obstacle is None or not direct.crosses(obstacle)):
        return np.asarray([start, target], dtype=float), float(direct.length)
    nodes = [np.asarray(start), np.asarray(target)]
    if obstacle is not None:
        coords = list(obstacle.exterior.coords[:-1])
        nodes += [np.asarray(p) for p in coords]
    n = len(nodes); edges = [[] for _ in nodes]
    for i in range(n):
        for j in range(i):
            segment = LineString([nodes[i], nodes[j]])
            if free.covers(segment) and (obstacle is None or not segment.crosses(obstacle)):
                d = float(np.linalg.norm(nodes[i]-nodes[j])); edges[i].append((j,d)); edges[j].append((i,d))
    dist=[float('inf')]*n; prev=[-1]*n; dist[0]=0.; queue=[(0.,0)]
    while queue:
        d,u=heapq.heappop(queue)
        if d != dist[u]: continue
        for v,w in edges[u]:
            if d+w < dist[v]: dist[v]=d+w; prev[v]=u; heapq.heappush(queue,(dist[v],v))
    if not np.isfinite(dist[1]): return None, float('inf')
    ids=[]; u=1
    while u >= 0: ids.append(u); u=prev[u]
    return np.asarray([nodes[i] for i in ids[::-1]]), dist[1]


def navigate_and_assign(guides, targets, room, wall_margin, crowd_polygon, crowd_margin):
    room_poly = Polygon([(0,0),(room[0],0),(room[0],room[1]),(0,room[1])]).buffer(-wall_margin)
    # Simplification is followed by a larger outward buffer, so graph size is
    # bounded without making the navigation obstacle less conservative.
    obstacle = crowd_polygon.buffer(crowd_margin, join_style='mitre').simplify(.10, preserve_topology=True).buffer(.11, join_style='mitre')
    free = room_poly.difference(obstacle)
    paths={}; cost=np.full((len(guides),len(targets)), np.inf)
    for i,g in enumerate(guides):
        for j,t in enumerate(targets):
            if free.covers(Point(g)) and free.covers(Point(t)):
                paths[i,j], cost[i,j] = _shortest(g,t,free,obstacle)
    finite=np.isfinite(cost)
    if not finite.any() or np.any(~finite.any(axis=0)):
        raise ValueError('PATH_UNREACHABLE: target has no path in conservative free space')
    penalty=np.where(finite,cost,1e12)
    rows,cols=linear_sum_assignment(penalty)
    keep=cols < len(targets); rows,cols=rows[keep],cols[keep]
    if len(set(cols)) != len(targets) or np.any(~finite[rows,cols]):
        raise ValueError('PATH_UNREACHABLE: reachable bipartite matching does not exist')
    assignment=np.full(len(guides),-1,dtype=int); assignment[rows]=cols
    ordered=tuple(paths[i,j] for i,j in zip(rows,cols))
    return NavigationResult(assignment,ordered,cost[rows,cols],finite)


def route_assigned(guides, targets, assignment, room, wall_margin,
                   crowd_polygon, crowd_margin):
    """Recompute paths for an existing guide-to-target identity mapping."""
    room_poly = Polygon([(0, 0), (room[0], 0), (room[0], room[1]),
                         (0, room[1])]).buffer(-wall_margin)
    obstacle = crowd_polygon.buffer(
        crowd_margin, join_style='mitre'
    ).simplify(.10, preserve_topology=True).buffer(.11, join_style='mitre')
    free = room_poly.difference(obstacle)
    paths = {}
    lengths = {}
    for guide in np.flatnonzero(np.asarray(assignment) >= 0):
        target = int(assignment[guide])
        if target >= len(targets) or not free.covers(Point(guides[guide])) \
                or not free.covers(Point(targets[target])):
            raise ValueError('PATH_UNREACHABLE: assigned endpoint is outside conservative free space')
        path, length = _shortest(guides[guide], targets[target], free, obstacle)
        if path is None:
            raise ValueError('PATH_UNREACHABLE: assigned guide-target path does not exist')
        paths[int(guide)] = path
        lengths[int(guide)] = length
    return paths, lengths

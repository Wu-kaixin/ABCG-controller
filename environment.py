"""JuPedSim static snapshot adapter. No human dynamics are advanced in Step 1.

Adapted from Crowd-Management crowd/jupedsim_static.py and heterogeneity.py.
Spawn geometry belongs here, never in the controller observation.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version

import jupedsim as jps
import numpy as np
from shapely.geometry import Polygon

from interfaces import LocalObservation
from scene import RectangularScenario


def positive(value, name: str, *, zero: bool = False) -> float:
    number = float(value)
    if not np.isfinite(number) or (number < 0 if zero else number <= 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if zero else 'positive'}")
    return number


def integer(value, name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def sample_attributes(count: int, config: dict, seed: int) -> dict[str, np.ndarray]:
    """Bounded independent samples; streams do not depend on scene generation."""
    if not isinstance(config.get("enabled", True), bool):
        raise ValueError("heterogeneity.enabled must be boolean")
    enabled = config.get("enabled", True)
    allowed = {"enabled", "radius", "desired_speed", "time_gap", "demand_weight"}
    if set(config) - allowed:
        raise ValueError(f"Unknown heterogeneity keys: {set(config) - allowed}")
    defaults = {
        "radius": (0.20, 0.015, 0.17, 0.23),
        "desired_speed": (1.25, 0.10, 0.95, 1.55),
        "time_gap": (1.0, 0.08, 0.80, 1.20),
        "demand_weight": (1.0, 0.12, 0.75, 1.25),
    }
    attributes = {"agent_id": np.arange(count, dtype=int)}
    for child, (name, default) in zip(np.random.SeedSequence(seed).spawn(4), defaults.items()):
        raw = config.get(name, {})
        if set(raw) - {"mean", "std", "min", "max"}:
            raise ValueError(f"Unknown {name} distribution keys")
        mean, std, low, high = [float(raw.get(k, d)) for k, d in zip(("mean", "std", "min", "max"), default)]
        if not np.all(np.isfinite([mean, std, low, high])) or std < 0 or low <= 0 or not low <= mean <= high:
            raise ValueError(f"Invalid bounded distribution for {name}")
        rng = np.random.default_rng(child)
        values = rng.normal(mean, std, count) if enabled else np.full(count, mean)
        attributes[name] = np.clip(values, low, high)
    return attributes


@dataclass
class StaticEnvironment:
    scenario: RectangularScenario
    _positions: np.ndarray
    attributes: dict[str, np.ndarray]
    jupedsim_version: str

    def observe(self) -> np.ndarray:
        """Return global Step-1 observations, never a spawn polygon or truth boundary."""
        return self._positions.copy()

    def observe_agent(self, guide_id: int, guides: np.ndarray, timestamp: float) -> LocalObservation:
        """Future local-policy seam; currently all guides and people are visible."""
        ids = tuple(i for i in range(len(guides)) if i != guide_id)
        return LocalObservation(guide_id, guides[guide_id].copy(), self.observe(), ids,
                                guides[list(ids)].copy(), float(timestamp))

    def advance(self, dt: float) -> None:
        positive(dt, "dt")
        # Intentionally frozen. Step 2 will implement JuPedSim Simulation.iterate.


def build_environment(config: dict) -> StaticEnvironment:
    if config.get("step") != 1:
        raise ValueError("Only step: 1 is implemented")
    sc = config["scene"]
    if set(sc) - {"type", "width", "height", "openings"}:
        raise ValueError("Unknown scene key")
    if sc.get("openings", []):
        raise ValueError("Step 1 requires a closed scene: openings must be []")
    scenario = RectangularScenario(str(sc["type"]), float(sc["width"]), float(sc["height"]), str(sc["type"]))
    crowd = config["crowd"]
    if set(crowd) - {"source", "static", "count", "spawn_vertices", "spacing", "spawn_margin", "heterogeneity"}:
        raise ValueError("Unknown crowd key")
    if crowd.get("static") is not True or crowd.get("source") != "jupedsim":
        raise ValueError("Step 1 requires source: jupedsim and static: true")
    seed = integer(config["simulation"]["seed"], "seed", 0)
    count = integer(crowd["count"], "crowd.count", 8)
    attributes = sample_attributes(count, crowd.get("heterogeneity", {}), seed)
    vertices = np.asarray(crowd["spawn_vertices"], dtype=float)
    if vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) < 3 or not np.isfinite(vertices).all():
        raise ValueError("spawn_vertices must be finite (N, 2), N >= 3")
    polygon = Polygon(vertices)
    room = Polygon(scenario.boundary_vertices())
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0 or not room.covers(polygon):
        raise ValueError("spawn polygon must be valid and contained in the scene")
    max_radius = float(np.max(attributes["radius"]))
    spacing = max(positive(crowd.get("spacing", 0.5), "spacing"), 2 * max_radius)
    margin = max(positive(crowd.get("spawn_margin", 0.25), "spawn_margin", zero=True), max_radius)
    positions = np.asarray(jps.distribute_by_number(
        polygon=polygon, number_of_agents=count, distance_to_agents=spacing,
        distance_to_polygon=margin, seed=seed,
    ), dtype=float)
    if positions.shape != (count, 2) or not np.isfinite(positions).all():
        raise RuntimeError("JuPedSim did not return the requested finite point cloud")
    # Own a read-only snapshot: no accidental crowd motion through shared arrays.
    positions.setflags(write=False)
    return StaticEnvironment(scenario, positions, attributes, version("jupedsim"))


def initialize_guides(config: dict, env: StaticEnvironment, crowd_distance: float,
                      pair_distance: float, wall_margin: float) -> np.ndarray:
    """Initialize independently of ABCG targets; report impossible layouts."""
    raw = config["guides"]
    count = integer(raw["count"], "guides.count")
    initial = raw["initialization"]
    if initial["type"] == "positions":
        if set(initial) != {"type", "positions"}:
            raise ValueError("positions initialization accepts only type and positions")
        guides = np.asarray(initial["positions"], dtype=float)
    elif initial["type"] == "perimeter":
        if set(initial) != {"type", "inset", "phase"}:
            raise ValueError("perimeter initialization requires type, inset and phase")
        inset = positive(initial["inset"], "guides.initialization.inset")
        if 2 * inset >= min(env.scenario.width, env.scenario.height):
            raise ValueError("guide perimeter inset is too large")
        width, height = env.scenario.width - 2 * inset, env.scenario.height - 2 * inset
        line = Polygon([(inset, inset), (inset+width, inset),
                        (inset+width, inset+height), (inset, inset+height)]).exterior
        phase = float(initial["phase"])
        if not np.isfinite(phase):
            raise ValueError("guide perimeter phase must be finite")
        guides = np.array([line.interpolate(((i/count + phase) % 1)*line.length).coords[0] for i in range(count)])
    else:
        raise ValueError("Unknown guide initialization type")
    if guides.shape != (count, 2) or not np.isfinite(guides).all():
        raise ValueError("guide positions must be finite and match guides.count")
    if not env.scenario.contains(guides, wall_margin).all():
        raise ValueError("guide initialization violates wall clearance")
    pairs = np.linalg.norm(guides[:, None] - guides[None, :], axis=2)
    np.fill_diagonal(pairs, np.inf)
    if pairs.min(initial=np.inf) < pair_distance:
        raise ValueError("guide initialization violates pair clearance")
    if np.linalg.norm(guides[:, None] - env.observe()[None, :], axis=2).min() < crowd_distance:
        raise ValueError("guide initialization violates crowd clearance")
    return guides

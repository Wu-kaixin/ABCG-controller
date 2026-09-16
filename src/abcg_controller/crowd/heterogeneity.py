"""Moderate pedestrian heterogeneity for the static Step-1 crowd model."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

Array = np.ndarray


@dataclass(frozen=True)
class HeterogeneityConfig:
    enabled: bool = True
    radius_mean: float = 0.20
    radius_std: float = 0.015
    radius_min: float = 0.17
    radius_max: float = 0.23
    preferred_speed_mean: float = 1.25
    preferred_speed_std: float = 0.10
    preferred_speed_min: float = 0.95
    preferred_speed_max: float = 1.55
    time_gap_mean: float = 1.00
    time_gap_std: float = 0.08
    time_gap_min: float = 0.80
    time_gap_max: float = 1.20

    def __post_init__(self) -> None:
        triples = (
            ("radius", self.radius_mean, self.radius_std, self.radius_min, self.radius_max),
            (
                "preferred_speed",
                self.preferred_speed_mean,
                self.preferred_speed_std,
                self.preferred_speed_min,
                self.preferred_speed_max,
            ),
            ("time_gap", self.time_gap_mean, self.time_gap_std, self.time_gap_min, self.time_gap_max),
        )
        for name, mean, std, lower, upper in triples:
            values = np.asarray([mean, std, lower, upper], dtype=float)
            if not np.all(np.isfinite(values)):
                raise ValueError(f"{name} parameters must be finite")
            if std < 0.0 or lower <= 0.0 or upper < lower or not lower <= mean <= upper:
                raise ValueError(f"invalid bounded distribution for {name}")


@dataclass(frozen=True)
class PedestrianAttributes:
    radius: Array
    preferred_speed: Array
    time_gap: Array

    def __post_init__(self) -> None:
        lengths = {len(np.asarray(self.radius)), len(np.asarray(self.preferred_speed)), len(np.asarray(self.time_gap))}
        if len(lengths) != 1:
            raise ValueError("all pedestrian attribute arrays must have the same length")


def _bounded_normal(
    rng: np.random.Generator,
    count: int,
    mean: float,
    std: float,
    lower: float,
    upper: float,
) -> Array:
    if std == 0.0:
        return np.full(count, mean, dtype=float)
    return np.clip(rng.normal(mean, std, size=count), lower, upper)


def sample_heterogeneity(
    count: int,
    seed: int,
    config: HeterogeneityConfig | None = None,
) -> PedestrianAttributes:
    """Return deterministic bounded attributes for ``count`` pedestrians.

    Step 1 keeps pedestrians static.  ``preferred_speed`` and ``time_gap`` are
    therefore stored for model continuity only and do not imply pedestrian
    motion or a validated heterogeneity effect.
    """

    if isinstance(count, bool) or not isinstance(count, (int, np.integer)) or count < 1:
        raise ValueError("count must be a positive integer")
    cfg = config or HeterogeneityConfig()
    rng = np.random.default_rng(int(seed))

    if not cfg.enabled:
        return PedestrianAttributes(
            radius=np.full(count, cfg.radius_mean, dtype=float),
            preferred_speed=np.full(count, cfg.preferred_speed_mean, dtype=float),
            time_gap=np.full(count, cfg.time_gap_mean, dtype=float),
        )

    return PedestrianAttributes(
        radius=_bounded_normal(rng, count, cfg.radius_mean, cfg.radius_std, cfg.radius_min, cfg.radius_max),
        preferred_speed=_bounded_normal(
            rng,
            count,
            cfg.preferred_speed_mean,
            cfg.preferred_speed_std,
            cfg.preferred_speed_min,
            cfg.preferred_speed_max,
        ),
        time_gap=_bounded_normal(rng, count, cfg.time_gap_mean, cfg.time_gap_std, cfg.time_gap_min, cfg.time_gap_max),
    )

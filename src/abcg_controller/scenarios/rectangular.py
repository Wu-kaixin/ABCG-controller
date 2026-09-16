"""Canonical Step-1 square/rectangle environments."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .base import Array, BoundaryOpening

ScenarioKind = Literal["square", "rectangle"]


@dataclass(frozen=True)
class RectangularScenario:
    """Axis-aligned bounded environment with future opening support.

    In Step 1, ``openings`` must remain empty.  The environment geometry is
    known workspace geometry; it must never be substituted for the unknown
    crowd boundary.
    """

    name: str
    width: float
    height: float
    kind: ScenarioKind
    openings: tuple[BoundaryOpening, ...] = ()

    def __post_init__(self) -> None:
        if not np.isfinite(self.width) or not np.isfinite(self.height):
            raise ValueError("width and height must be finite")
        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError("width and height must be positive")
        if self.kind == "square" and not np.isclose(self.width, self.height):
            raise ValueError("square scenario requires width == height")
        if self.kind not in {"square", "rectangle"}:
            raise ValueError("kind must be 'square' or 'rectangle'")
        for opening in self.openings:
            wall_length = self.height if opening.wall in {"left", "right"} else self.width
            if opening.end > wall_length:
                raise ValueError("opening extends beyond its wall")

    @classmethod
    def square(cls, side: float, name: str = "square_closed") -> "RectangularScenario":
        return cls(name=name, width=float(side), height=float(side), kind="square")

    @classmethod
    def rectangle(
        cls,
        width: float,
        height: float,
        name: str = "rectangle_closed",
    ) -> "RectangularScenario":
        return cls(name=name, width=float(width), height=float(height), kind="rectangle")

    @property
    def closed(self) -> bool:
        return len(self.openings) == 0

    def boundary_vertices(self) -> Array:
        return np.array(
            [
                [0.0, 0.0],
                [self.width, 0.0],
                [self.width, self.height],
                [0.0, self.height],
            ],
            dtype=float,
        )

    def contains(self, points: Array, margin: float = 0.0) -> Array:
        values = np.asarray(points, dtype=float)
        if values.ndim != 2 or values.shape[1:] != (2,) or not np.all(np.isfinite(values)):
            raise ValueError("points must be a finite (N, 2) array")
        clearance = float(margin)
        if not np.isfinite(clearance) or clearance < 0.0:
            raise ValueError("margin must be finite and non-negative")
        if 2.0 * clearance > min(self.width, self.height):
            return np.zeros(len(values), dtype=bool)
        return (
            (values[:, 0] >= clearance)
            & (values[:, 0] <= self.width - clearance)
            & (values[:, 1] >= clearance)
            & (values[:, 1] <= self.height - clearance)
        )

    def step1_contract_valid(self) -> bool:
        return self.closed

"""Environment contracts shared by Step 1 and future scenario extensions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

Array = np.ndarray
WallName = Literal["left", "right", "bottom", "top"]


@dataclass(frozen=True)
class BoundaryOpening:
    """Reserved representation for a future wall opening.

    Step 1 closed scenarios use no openings.  Step 2 may activate this
    contract without changing the ABCG controller API.
    """

    wall: WallName
    start: float
    end: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.start) or not np.isfinite(self.end):
            raise ValueError("opening endpoints must be finite")
        if self.start < 0.0 or self.end <= self.start:
            raise ValueError("opening must satisfy 0 <= start < end")


class Scenario(Protocol):
    """Minimal geometry contract consumed by experiment/safety layers."""

    name: str
    width: float
    height: float
    openings: tuple[BoundaryOpening, ...]

    @property
    def closed(self) -> bool: ...

    def boundary_vertices(self) -> Array: ...

    def contains(self, points: Array, margin: float = 0.0) -> Array: ...

    def step1_contract_valid(self) -> bool: ...

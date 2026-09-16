"""Data shared by the environment and controller; local policy is a future seam."""
from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Observation:
    positions: np.ndarray
    radii: np.ndarray
    demand: np.ndarray


@dataclass(frozen=True)
class NeighborMessage:
    sender: int
    timestamp: float
    payload: dict


class LocalPolicy(Protocol):
    """Reserved for Step 3. Step 1 still uses global observations and control."""
    def velocity(self, own_position: np.ndarray, observation: Observation,
                 messages: tuple[NeighborMessage, ...]) -> np.ndarray: ...

"""Controller contracts for the restarted Step-1 ABCG implementation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

Array = np.ndarray


@dataclass(frozen=True)
class ControlOutput:
    """One measured-feedback control output."""

    preferred_velocity: Array
    applied_velocity: Array
    state: str
    diagnostics: dict[str, object]


class ABCGController(Protocol):
    """Stable interface for the Step-1 controller implementation.

    The concrete controller may evolve internally while experiments keep this
    measured-feedback contract.  The controller receives crowd observations,
    not evaluator-only crowd/spawn truth.
    """

    def reset(self, guide_state: Array, target_positions: Array) -> None: ...

    def step(self, crowd_observation: Array, guide_state: Array, dt: float) -> ControlOutput: ...

"""Reserved local-sensing/local-communication contracts for future Step 3.

These interfaces are intentionally not activated by the Step-1 experiments.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

Array = np.ndarray


@dataclass(frozen=True)
class LocalObservation:
    guide_id: int
    guide_position: Array
    pedestrian_positions: Array
    neighbor_guide_ids: tuple[int, ...]
    neighbor_guide_positions: Array
    timestamp: float


@dataclass(frozen=True)
class NeighborMessage:
    sender_id: int
    timestamp: float
    payload: dict[str, object]


@dataclass(frozen=True)
class CrowdGroupHypothesis:
    group_id: int
    centroid: Array
    member_count: int
    confidence: float


@dataclass(frozen=True)
class DistributedResourceProposal:
    guide_id: int
    group_id: int
    utility: float


class DecentralizedGuidePolicy(Protocol):
    """Future Step-3 policy contract; no Step-1 implementation is provided."""

    def step(
        self,
        observation: LocalObservation,
        messages: tuple[NeighborMessage, ...],
    ) -> Array: ...

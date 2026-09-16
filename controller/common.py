"""Small numerical helpers retained from Crowd-Management/types.py."""
import numpy as np

Array = np.ndarray


def unit(vec: Array, fallback: Array | None = None) -> Array:
    size = float(np.linalg.norm(vec))
    if size < 1e-9:
        return np.zeros(2, dtype=float) if fallback is None else unit(fallback)
    return np.asarray(vec, dtype=float) / size

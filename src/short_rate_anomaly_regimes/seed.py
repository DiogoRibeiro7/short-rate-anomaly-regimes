"""Deterministic random-seed utilities."""

from __future__ import annotations

import random

import numpy as np
from numpy.typing import NDArray


def seed_everything(seed: int) -> np.random.Generator:
    """Seed Python and NumPy global generators and return a local generator."""
    random.seed(seed)
    np.random.seed(seed)
    return np.random.default_rng(seed)


def bootstrap_indices(
    *,
    observations: int,
    draws: int,
    seed: int,
) -> NDArray[np.int64]:
    """Draw deterministic row indices for nonparametric bootstrap samples."""
    if observations <= 0:
        raise ValueError("observations must be positive")
    if draws <= 0:
        raise ValueError("draws must be positive")
    rng = np.random.default_rng(seed)
    return rng.integers(0, observations, size=(draws, observations), dtype=np.int64)

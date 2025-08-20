"""Utilities for saving and loading NumPy arrays and metadata to/from cache."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def save_grid(path: str, grid_array: np.ndarray, metadata: Dict[str, Any]) -> None:
    """Saves a NumPy grid and its metadata to a compressed .npz file.

    The metadata dictionary is serialized to a JSON string.

    Args:
        path: The file path to save to.
        grid_array: The NumPy array containing the grid data.
        metadata: A dictionary of metadata associated with the grid.
    """
    try:
        meta_json = json.dumps(metadata)
        np.savez_compressed(path, grid=grid_array, meta=meta_json)
        logger.debug(f"Successfully saved grid and metadata to {path}")
    except (TypeError, OSError) as e:
        logger.exception(f"Failed to save grid to {path}: {e}")
        raise


def load_grid(path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Loads a NumPy grid and its metadata from a .npz file.

    The metadata is deserialized from a JSON string.

    Args:
        path: The file path to load from.

    Returns:
        A tuple containing the grid array and the metadata dictionary.
    """
    try:
        with np.load(path) as data:
            grid_array = data["grid"]
            meta_json = data["meta"].item()  # .item() extracts scalar from 0-d array
            metadata = json.loads(meta_json)
            logger.debug(f"Successfully loaded grid and metadata from {path}")
            return grid_array, metadata
    except (IOError, KeyError, json.JSONDecodeError) as e:
        logger.exception(f"Failed to load grid from {path}: {e}")
        raise

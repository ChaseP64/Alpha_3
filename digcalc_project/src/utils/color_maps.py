import matplotlib.cm
import matplotlib.colors
import numpy as np


def dz_to_rgba(dz: np.ndarray, clip: float = 5.0) -> np.ndarray:
    """Convert a delta-Z (elevation difference) array to an RGBA image.

    Uses a Red-Blue diverging colormap ('RdBu_r') where negative values (cut)
    are red, positive values (fill) are blue, and values near zero are white.
    The input `dz` array is clipped to the range [-clip, +clip] before normalization.

    Args:
        dz (np.ndarray): A 2D numpy array of elevation differences.
        clip (float): The absolute value to clip the dz range to. Differences
                      outside [-clip, +clip] will be mapped to the end colors.
                      Defaults to 5.0.

    Returns:
        np.ndarray: An (H, W, 4) numpy array of uint8 RGBA values. Alpha is set
                    to 180 (out of 255) for slight transparency.

    """
    cmap = matplotlib.cm.get_cmap("RdBu_r")
    # Normalize dz values to [0, 1] after clipping
    # norm = np.clip(dz / clip, -1, 1) * 0.5 + 0.5
    # More robust normalization handling potential division by zero if clip is 0
    norm = matplotlib.colors.Normalize(vmin=-clip, vmax=clip)
    normalized_dz = norm(dz)

    # Apply the colormap
    # cmap returns float values in [0, 1], scale to [0, 255] and convert to uint8
    rgba = (cmap(normalized_dz) * 255).astype(np.uint8)

    # Set a global alpha value (e.g., 180 for some transparency)
    rgba[..., 3] = 180
    return rgba

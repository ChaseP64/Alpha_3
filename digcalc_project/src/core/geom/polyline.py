from __future__ import annotations

"""digcalc_project.src.core.geom.polyline

Light-weight Polyline data model shared by geometry and UI layers.
This is the initial scaffold added in *PDF Vectorizer MVP – Step 1*.
Concrete geometry helpers will arrive in later steps.
"""

from typing import Optional, Tuple, Sequence, Iterable, List

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field, ConfigDict

__all__ = ["Polyline"]


class Polyline(BaseModel):
    """Simple 2-D polyline.

    All coordinates are expressed in *world* units (not pixels).
    Additional metadata (stroke colour, dash pattern, source page) are
    carried so that importers such as *pdf_vectorizer* can round-trip
    styling information and build heuristics.
    """

    vertices: npt.NDArray[np.float64] = Field(..., description="(N,2) array of XY vertices")
    stroke_rgb: Optional[Tuple[int, int, int]] = Field(
        default=None, description="RGB stroke colour captured from source drawing (0-255)"
    )
    dash: Optional[Tuple[float, ...]] = Field(
        default=None, description="Dash/gap pattern in world units, if original path was dashed"
    )
    src_page: Optional[int] = Field(
        default=None, description="1-based PDF page number this polyline came from"
    )

    # pydantic config – allow numpy arrays without conversion to list
    model_config = ConfigDict(arbitrary_types_allowed=True, validate_default=True)

    # ------------------------------------------------------------------
    # Convenience helpers – **placeholders**, real logic lands in step 3
    # ------------------------------------------------------------------
    def __len__(self) -> int:  # pragma: no cover – trivial
        return int(self.vertices.shape[0])

    @staticmethod
    def join_colinear(polylines: Sequence["Polyline"], tolerance: float = 1e-6) -> List["Polyline"]:
        """Placeholder for colinear-join routine.

        Later steps will merge dashed contour segments into a single
        continuous polyline.  For now we return the input unchanged.
        """

        # TODO: implement in Step 3
        return list(polylines) 
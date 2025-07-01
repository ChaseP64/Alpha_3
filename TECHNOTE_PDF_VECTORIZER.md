# PDF Vectorizer – Technical Notes

This document explains the architecture, algorithms, and practical
considerations behind **DigCalc's PDF Vectorizer** feature that converts
vector‐based construction drawings into editable polylines.

> The implementation lives primarily in
> `digcalc_project/src/services/io/pdf_vectorizer.py` and is surfaced in the GUI
> through `ImportVectorDialog` and the *Vectorize Current PDF Page…* action.

---

## 1. Pipeline Overview

```mermaid
flowchart LR
    subgraph Extraction
        A[fitz.Page] -->|get_drawings()| B[raw drawing dicts]
        B -->|_extract_graphics| C[Polyline + style]
    end

    C --> D[group_by_style]
    D --> E[_merge_dashes]
    E --> F[join_colinear]
    F --> G[smart_clean.auto_run]
    G --> H[Polylines ready]
```

1. **Extraction** – PyMuPDF (`fitz`) provides low-level stroke segments on a
   page.  `_extract_graphics` walks these structures, converts *paths* and *l*
   items into `Polyline` objects, and attaches colour / dash style.
2. **Grouping** – `group_by_style` partitions the list by `(stroke_rgb, dash)`
   key so subsequent passes can treat visually identical strokes together.
3. **Dash Merge** – `_merge_dashes` examines adjacent *dash segments* and joins
   them into a single continuous polyline when the gap is within tolerances.
4. **Colinear Simplification** – `Polyline.join_colinear` collapses vertices
   that lie on the same line (angle ≤ 1° & distance ≤ 1 × 10⁻³ units).
5. **Smart Clean** – lightweight NumPy hashing removes exact duplicates and
   near-zero length polylines.

The entire process is pure-Python/NumPy – no external C-extensions besides
PyMuPDF – and therefore easy to run in restricted CI environments.

---

## 2. Coordinate Scaling

PDF coordinates are expressed in *PostScript points* (¹⁄₇₂ inch).  DigCalc works
in **world units** (feet or metres) so we apply an **affine transform**:

\[ \mathbf P_{world} = s \; \mathbf P_{pt} + \mathbf o \]

where

* `s` – scale factor (= *world-units / pt*).  For example, a sheet at
  1 in = 20 ft yields `s = 20 ft / 72 pt ≈ 0.2778`.
* `o` – 2-D translation that positions the sheet origin chosen by the user.

Both values are supplied by the `ImportVectorDialog` once the user calibrates
scale and picks an origin handle.

---

## 3. Performance Guard

Large architectural drawings can contain **hundreds of thousands** of segments.
To avoid UI stalls and memory explosions we use two safeguards:

1. **Batch Iterator** – `vectorize()` yields progress every **5 000 segments**
   via an optional `progress_cb(done, total)` allowing the dialog to update a
   progress bar while keeping the Qt event‐loop responsive.
2. **Bail-Out Check** – if the total segment count exceeds **250 k** the user
   is prompted to *Crop or Continue*.  Cancelling aborts vectorization before
   heavy post-processing.

Benchmark (`tests/benchmarks/test_pdf_vectorizer_bench.py`) shows that a
10 MB structural plan (~45 k segments) completes in **< 1 s** on a 2022 laptop.

---

## 4. Extending the Vectorizer

* **Curve Support** – `_path_to_polyline` currently relies on PyMuPDF's built-in
  flattening.  For higher fidelity consider adaptive subdivision based on
  curvature.
* **Layer Detection** – many drawings encode layers via colours/line-styles.
  `group_by_style` already surfaces this info; expand `_groups → layer mapping`
  rules in `ImportVectorDialog` for smarter defaults.
* **Parallel Post-Processing** – `_post_process` is embarrassingly parallel.
  Future work could `concurrent.futures.ThreadPoolExecutor` the per-style merge
  & simplify steps.

---

## 5. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| "ValueError: malformed path object" | Corrupt vector element in PDF | Re-export the sheet from CAD or rasterize the problematic page. |
| Dialog progress bar stuck at 0 % | `progress_cb` not wired – ensure you call `ImportVectorDialog.run_vectorization()` instead of `PDFVectorizer.vectorize()` directly. |
| Polylines appear offset | Verify the *origin* point matches the expected (0, 0) in world coordinates. |

---

© 2025 DigCalc Dev Team 
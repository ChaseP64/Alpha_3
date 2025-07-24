# Changelog

All notable changes to this project will be documented in this file.  The
format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0-vectorizer] – 2025-07-01

### Added

* **PDF Vectorizer MVP** – import native vector strokes from PDF sheets
  (see `TECHNOTE_PDF_VECTORIZER.md`).
* `ImportVectorDialog` with live preview + layer mapping.
* `Vectorize Current PDF Page…` UI action (feature-flagged by
  `DIGCALC_PDF_VEC=1`).
* Batch progress updates, bail-out guard (>250 k segments), performance
  benchmark, random-PDF fuzz runner, and GitHub workflow.

### Changed

* Bumped application version to **0.9.0-vectorizer**.
* `pyproject.toml` now pins `PyMuPDF` to `>=1.24,<1.25`.

### Migration Notes

1. **Environment Variable** – set `DIGCALC_PDF_VEC=1` to enable the new menu
   entry.  The default in CI remains disabled.
2. **Dependencies** – run `pip install -r requirements.txt` to pick up the
   updated `PyMuPDF` pin if your environment was using a pre-1.24 build.
3. **CI** – adopt the new workflow `.github/workflows/vectorizer-tests.yml` or
   add the env vars to your own pipeline to exercise the vectorizer tests.

## [0.10.0-elevation] – 2025-07-24

### Added
* **Phase 5 complete – Elevation Tools**: Auto-Increment wizard, Batch Elevate dialog, and ultra-fast Elevation Heat-Map preview (<100 ms for 10 k vertices).

--- 
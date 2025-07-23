DigCalc — Phases 2 & 3 Execution Checklist
(Authoritative TODO board – every unchecked bullet is an outstanding task)
================================================================
Phase 2 — Smart Clean + Classification & Join Fidelity
Branch feature/phase-2-clean-classify  ETA ≈ 5 dev-days (2 devs)
================================================================
from updated master/main
git checkout -b feature/phase-2-clean-classify
D1 – Rule Engine Skeleton & Dialog Stub
[x] Create core/clean/rule_engine.py with BaseRule, RuleRegistry, evaluate() — implemented (2025-07-15)
[x] Wire RuleEngine into existing cleaners.smart_clean.auto_run() — integrated pipeline (2025-07-15)
[x] Add SmartCleanDialog stub (ui/dialogs/smart_clean_dialog.py) with enable/disable checkbox — sliders added for tolerances (2025-07-15)
[x] Expose toolbar/menu action → opens dialog (toolbar, menu, signal wiring complete)
[x] Unit tests: tests/clean/test_rule_engine_basics.py — passing
D2 – Automatic Join V2 & Smart Clean Upgrade
[x] Implement Polyline.auto_join_v2() (angle + gap bridge, preserves corners)
[x] Extend RuleEngine with “GapCloseRule”, “LayerClassifyRule”
[x] Upgrade cleaners.smart_clean.auto_run() to call join V2 then apply rules
[x] CLI flag & SettingsService toggle: enable_auto_join_v2 (settings key added)
[ ] Unit tests + golden-file diffs for join fidelity  (golden diff harness ready; baseline diff TODO)
D3 – Two-Phase Compression + Preferences UI
[x] Add Polyline.compress(dist_tol, angle_tol) & Polyline.compress_hq()
[x] Create Preferences tab “Smart-Clean” with sliders for dist_tol & angle_tol (live preview)
[x] Persist prefs via SettingsService; load defaults 0.10 ft / 0.01 ft
[x] End-to-end test with pytest-qt: user changes tolerance → smart-clean respects new values (unit test passes)
D4 – Golden-File Harness & GUI Tests
[x] Add tests/golden/__init__.py helper to read/write serialized polylines
[ ] Baseline goldens for sample_site.pdf after Smart-Clean pass
[ ] Playwright (or pytest-qt) macro: import PDF → wait → assert golden diff < 0.5 %
[ ] CI job smart_clean_golden runs on every PR
D5 – Polish & Merge Prep
[ ] README / TECHNOTE updates for Smart-Clean & classification
[ ] Changelog entry “Phase 2 complete”
[ ] Code-style sweep (black, isort, flake8) & docstrings
[ ] Raise PR to master → satisfy merge gate
Merge gate / exit criteria (all must pass)
✅ 100 % unit-test & GUI-test pass on CI (Linux, macOS, Windows)
✅ Golden-file diff ≤ 0.5 % for sample_site.pdf
✅ Coverage ≥ 90 % for core.clean & geom.polyline modules
✅ No file > 500 lines (rule check script green)
✅ Docs (README/CHANGELOG) updated; lead dev approval + 1 peer review
================================================================
Phase 3 — Polyline Editing & Snapping Foundations
Branch feature/phase-3-edit-snap  ETA ≈ 5 dev-days (2 devs)
================================================================
start after Phase 2 PR merges
git checkout master
git pull
git checkout -b feature-3-edit-snap
D1 – Command Objects & Undo Stack Hooks
[x] Introduce ui.commands.edit_polyline.* (AddVertexCmd, DeleteVertexCmd, SplitCmd, JoinCmd)
[x] Integrate with existing MainWindow.undo_stack & menu shortcuts — implemented (2025-07-21)
[x] Unit tests: command applies, undo/redo restores state — implemented (2025-07-21)
D2 – Quad-Tree Spatial Index
[x] Add utils.spatial_index.QuadTree with insert/query(radius)
[x] Populate index in TracingScene for hover & snap queries — implemented (2025-07-21)
[x] Benchmark vs naïve search (pytest-bench) — passing (2025-07-21)
D3 – Shift-Override, Grid Snap, Heat-Map Overlay
[x] Implement grid-snap (1 ft default) toggled by Shift key — implemented (2025-07-21)
[ ] Add heat-map overlay to show snap density (optional visual)
[x] SettingsService option: enable_heatmap_overlay — implemented (2025-07-21)
[ ] GUI tests: Shift-drag snaps to grid; overlay toggles (unit-level snap tests added)
D4 – Perf Guards & GUI Regression Macros
[x] Detect > 50k-vertex edits → show warning & suggest batch mode — implemented (2025-07-21)
[x] Record Playwright macro: batch-join (J-key) on road centerlines — placeholder test added (2025-07-21)
[ ] Add regression suite to CI (tests/gui_macros/)
D5 – Final QA & Merge Prep
[ ] Update CHANGELOG & README (Polyline Editing)
[ ] Refactor oversize files if any grew > 500 lines
[ ] Green CI; raise PR to master
Merge gate / exit criteria
✅ All unit, GUI & macro tests green
✅ Quad-Tree query < 2 ms for 50k points (benchmarked)
✅ Editing commands fully undo/redo with no memory leaks (detected via tracemalloc in CI)
✅ Docs & demo video attached; 2 approvals
================================================================
Weekly demo script (Friday PM)
Import sample_site.pdf → auto-classify & Smart-Clean (Phase 2).
Open Smart-Clean log → show gaps closed & exported layer-map diff CSV.
Press J to batch-join road centerlines, demonstrate snap hints & Shift-override (Phase 3).
Run pytest-bench live → display timing SLA compliance for Quad-Tree queries and Smart-Clean
================================================================
Phase 4 — Snapping & Magnet Mode
Branch feature/phase-4-snap-magnet  ETA ≈ 4 dev-days (2 devs)
================================================================
start after Phase 3 PR merges
```
$ git checkout master
$ git pull
$ git checkout -b feature/phase-4-snap-magnet
```
D1 – Point / Edge Snap Hook-Up
[x] Extend utils.spatial_index.QuadTree with nearest-edge queries (projected distance)
[x] Implement point-snap (vertex-to-vertex) in ui/tracing_scene.py
[x] Implement edge-snap (perpendicular projection) in ui/tracing_scene.py
[x] Unit tests + pytest-bench scaffold (opt-in) added; perf CI job to enforce SLA

D2 – Shift-Disable Override & UI Affordance
[x] Integrate Shift key to temporarily disable snap (resolve overlap with grid-snap)
[x] Cursor/magnet icon when snap active
[x] SettingsService flag: enable_snap_default (persisted)

D3 – Perf Regression Guard
[ ] Benchmarks for 10 k & 50 k vertex datasets
[ ] CI fails if p50 > 1 ms (10 k) or > 2 ms (50 k)

Merge gate / exit criteria
✅ All new unit, GUI & benchmark tests green
✅ Point & edge snap honoured in tracing demo
✅ Quad-Tree query ≤ 1 ms (10 k verts), ≤ 2 ms (50 k verts)
✅ Docs & CHANGELOG updated; 1 demo GIF

================================================================
Phase 5 — Elevation UX Sprint
Branch feature/phase-5-elev-ux  ETA ≈ 3 dev-days (2 devs)
================================================================
D1 – Auto-Increment Wizard
[x] Dialog: pick first & last vertex Z → auto-fill intermediate vertices with linear grade (2025-07-23)
[x] Support ± slope percentage or explicit end-elevation (2025-07-23)
[x] Unit tests: interpolation accuracy & undo integration (2025-07-23)

D2 – Batch Elevate Dialog
[x] Multi-select polylines → set uniform Z or slope (2025-07-23)
[x] Single grouped undo command (2025-07-23)
[x] GUI test (pytest-qt): batch elevate 3 polylines (2025-07-23)

D3 – Elevation Heat-Map Preview
[x] Toggle in TracingScene to color-map vertices by Z range (2025-07-23)
[ ] Refresh ≤ 100 ms for 10 k vertices
[x] Persist preview flag via SettingsService (2025-07-23)

Exit criteria
✅ Wizards functional in headless tests
✅ Heat-map toggle persists & performant
✅ Docs & screenshots updated

================================================================
Phase 6 — Auto Classification
Branch feature/phase-6-classify  ETA ≈ 3 dev-days (1 dev + 0.5 review)
================================================================
D1 – Heuristic Classifier
[ ] Assign layer based on stroke RGB distance & OCR text labels
[ ] Plug into core/clean/rule_engine.py

D2 – Bulk “Assign Surface” Panel
[ ] Table of unclassified polylines with dropdown per row
[ ] Apply selection → updates project layers & refresh views
[ ] Unit tests: ≥ 90 % auto-tag accuracy on sample plans

Merge gate / exit criteria
✅ sample_site.pdf auto-tags ≥ 90 %
✅ Bulk override UI works & persists
✅ Golden diff updated for classify pipeline

================================================================
Phase 7 — Surface Debug View
Branch feature/phase-7-surface-debug  ETA ≈ 2 dev-days (1 dev)
================================================================
D1 – Un-elevated Vertex Highlighter
[ ] Highlight zero-Z vertices after import/editing

D2 – Dangling Edge Detector
[ ] Detect open contour chains / TIN holes

D3 – TIN Preview Overlay
[ ] Generate on-demand mesh preview in VisualizationPanel
[ ] Render toggle, refresh ≤ 500 ms for 10 k vertices

Exit criteria
✅ Debug view flags all issues in demo project
✅ No perf impact when disabled

================================================================
Phase 8 — Stripping Zones & Templates
Branch feature/phase-8-stripping  ETA ≈ 2 dev-days (2 devs)
================================================================
D1 – Stripping Zone Tool
[ ] Polygon tool to mark stripping area + depth/material

D2 – Template Library
[ ] CRUD dialog for templates (pad, road trench, etc.)
[ ] Template preview in plan & profile views

Exit criteria
✅ Stripping volumes integrate with VolumeCalculator
✅ Templates saved in Project file & reloaded

================================================================
Phase 9 — Perf & Polish
Branch feature/phase-9-polish  ETA ≈ 3 dev-days
================================================================
[ ] Nightly performance regression workflow (separate CI job) – alerts on SLA breach
[ ] Enable GitHub Dependabot & license scan; address top-severity issues
[ ] Add .gitattributes to enforce LF endings & unify diff
[ ] Retire stale feature flags, document remaining toggles
[ ] Profile & optimise QuadTree, Smart-Clean & vectorizer paths
[ ] Sweep for files > 500 lines; refactor
[ ] black, isort, flake8, docstrings pass
[ ] Update README/CHANGELOG; create release tag

Merge gate
✅ All CI & benchmarks within SLA
✅ Docs complete; release note approved

----------------------------------------------------------------
Weekly demo additions (rolling)
• Show snap vs shift-override (Phase 4)
• Elevation heat-map & batch elevate (Phase 5)
• Auto-classification accuracy table (Phase 6)
• TIN debug overlay toggle (Phase 7)
• Stripping template applied on sample project (Phase 8)

===============================================================
Buffer Week — Integration / Bug-Bash & Hardening
Branch chore/buffer-integration  ETA = 5 calendar days (shared)
===============================================================
Objective: catch cross-feature regressions, polish UI consistency, clear backlog bugs before stacking new complexity.

Tasks
[ ] End-to-end exploratory test sweep on Windows/macOS/Linux
[ ] Review goldens after Phase 5 – update & commit where behaviour is expected (Owner: **Alice**)
[ ] Execute nightly perf workflow dry-runs; adjust thresholds
[ ] Triage and close ≥ 90 % of open Phase ≤ 5 bugs
[ ] Produce consolidated UX critique & apply rapid fixes (< 2 h each)

Exit criteria
✅ CI green incl. nightly perf & golden diff jobs
✅ All demo scripts run without manual work-arounds
✅ Remaining open bugs labelled & scoped into later phases

===============================================================
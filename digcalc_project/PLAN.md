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
[ ] Integrate with existing MainWindow.undo_stack & menu shortcuts
[ ] Unit tests: command applies, undo/redo restores state
D2 – Quad-Tree Spatial Index
[x] Add utils.spatial_index.QuadTree with insert/query(radius)
[ ] Populate index in TracingScene for hover & snap queries
[ ] Benchmark vs naïve search (pytest-bench)
D3 – Shift-Override, Grid Snap, Heat-Map Overlay
[ ] Implement grid-snap (1 ft default) toggled by Shift key
[ ] Add heat-map overlay to show snap density (optional visual)
[ ] SettingsService option: enable_heatmap_overlay
[ ] GUI tests: Shift-drag snaps to grid; overlay toggles
D4 – Perf Guards & GUI Regression Macros
[ ] Detect > 50k-vertex edits → show warning & suggest batch mode
[ ] Record Playwright macro: batch-join (J-key) on road centerlines
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
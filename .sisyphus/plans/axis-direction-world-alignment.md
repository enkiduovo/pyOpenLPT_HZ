# Plan: Axis-Direction World Coordinate Alignment

## TL;DR
> **Summary**: Add optional post-calibration axis-direction world-coordinate alignment. After calibration finishes, if 2D axis points exist (from UI detection or CSV load), reconstruct 3D landmarks, compute closest orthonormal basis via SVD, apply rigid transform to cameras + 3D points (+ refraction plates if present), and re-render 3D viewer.
> **Deliverables**: CSV loader button; shared alignment helper; pinhole finalization bug fix; mode-specific adapters; post-calibration hooks; script-based validation.
> **Effort**: Medium (≈12–15 focused tasks across 4 waves)
> **Parallel**: YES — 5–8 tasks per wave after Wave 1 prerequisites
> **Critical Path**: Bug fix → Shared helpers → Mode adapters → Integration hooks → Validation

## Context

### Original Request
User requested an optional post-calibration step to align world coordinates to detected 3D axis directions. Axis points can come from:
1. Custom-axis detection UI (existing; already saves 2D points)
2. CSV file load (new; must implement)

Once axis points are available, system should:
1. Reconstruct 3D landmarks (center, +X, +Y, +Z) using calibrated camera parameters
2. Compute axis direction unit vectors
3. Orthogonalize to strict right-handed basis (closest to calculated directions) via SVD
4. Apply rigid transform (R, t) to all cameras, 3D points, and refraction plates
5. Re-render 3D viewer with aligned state

This is **optional**; if no axis points exist, no alignment occurs.

### Interview Summary
- **User confirmed** (via Q&A):
  - Prerequisite bug fix: YES (state-frame mismatch in pinhole finalization)
  - Timing: Immediately after calibration finalization
  - Failure handling: All-or-nothing guard (revert if any landmark fails)
  - Test strategy: Script-based validation (no pytest)
  - Re-alignment: Not required (one-time per calibration)
- **Metis gap analysis** identified 8 critical design areas with guardrails and acceptance criteria

### Metis Review
Metis identified **critical guardrails**:
- Triangulation robustness: Require 2+ cameras per landmark; fail all-or-nothing if any fails
- SVD degeneracy: Check condition number, singular values; require full-rank 3×3
- CSV validation: Accept partial axis data (subset of cameras)
- Refraction plate transform: `R @ n` for normals; verify plane position consistency
- Viewer coherence: Refresh wand-length display, residuals; document stale values
- Undoable state: Not required (one-time per calibration)
- CSV button placement: Require axis-point data to be present (non-empty `axis_direction_map`)
- Acceptance test: Verify reprojection errors, orthogonality (||R||=1, det=+1), centroid≈0

## Work Objectives

### Core Objective
Enable optional post-calibration world-coordinate alignment to user-detected 3D axis directions for both pinhole and refractive wand calibration in OpenLPT GUI. Provide CSV-based persistence and automated GUI integration.

### Deliverables
1. Bug fix for pinhole finalization state consistency
2. CSV loader for axis points with 9-column format
3. Shared alignment helper with triangulation adapters (pinhole + refractive)
4. SVD-based orthogonalization to right-handed basis
5. Integration hooks in pinhole and refractive completion flows
6. "Load Axis Points" button in UI below "Load Wand Points"
7. Script-based validation (synthetic setup + geometry checks + numeric thresholds)
8. Re-rendered 3D viewer after successful alignment

### Definition of Done (Verifiable)
1. [ ] Pinhole finalization produces consistent state (same world frame for `final_params` and `points_3d`)
2. [ ] CSV loader successfully reads 9-column format and populates `axis_direction_map`
3. [ ] Axis alignment computes orthonormal basis with `||R||=1` (within 1e-10) and `det(R)=+1`
4. [ ] All 4 landmarks (center, +X, +Y, +Z) triangulate with 2+ cameras per point (or fail all-or-nothing)
5. [ ] Rigid transform applied atomically to cameras, 3D points, and refraction plates
6. [ ] 3D viewer re-rendered showing transformed state with axis directions still visible
7. [ ] Script-based validation confirms reprojection errors within tolerance
8. [ ] "Load Axis Points" button appears when axis data exists; disabled during/after alignment

### Must Have
- Prerequisite bug fix (state consistency)
- SVD polar decomposition for orthogonalization
- All-or-nothing failure guard
- Both pinhole and refractive modes supported
- CSV loading with validation
- Post-calibration hook points

### Must NOT Have (Guardrails)
- Modifying intrinsic camera matrix `K` (rotation only)
- Modifying distortion coefficients `dist`
- Scale or shear transforms (rigid only)
- Alignment applied during optimization (post-calibration only)
- Re-alignment strategy (one-time per calibration)
- Partial-landmark alignment (all 4 or none)

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — all verification is agent-executed.

### Test Decision
**Script-based validation** (not pytest). Pattern: Synthetic 2-camera setup with known ground truth → triangulation → orthogonalization → transform application → reprojection validation → acceptance thresholds.

Reuse existing pattern from `.sisyphus/test_bootstrap_v2.py`:
- Synthetic observation generation
- Intrinsic/extrinsic matrix construction
- Triangulation + reprojection metrics
- Numeric acceptance criteria
- Exit 0/1 verdict

### QA Policy
Every task has agent-executed scenarios (happy path + failure paths). Evidence saved to `.sisyphus/evidence/task-{N}-{slug}.*`

### Evidence Artifacts
- Triangulation test: `.sisyphus/evidence/task-4-triangulation-accuracy.txt` (residuals)
- Orthogonalization test: `.sisyphus/evidence/task-5-orthogonality-metrics.txt` (||R||, det(R), singular values)
- Integration test: `.sisyphus/evidence/task-6-alignment-e2e.txt` (before/after reprojection)
- Full regression: `.sisyphus/evidence/task-9-full-regression.txt` (py_compile + script validation)

## Execution Strategy

### Parallel Execution Waves

**Wave 1: Prerequisite + Scaffold** (3 tasks, no interdependencies)
- Task 1: Fix pinhole finalization state-frame bug
- Task 2: Create test scaffold + validation baseline
- Task 3: Map axis-direction-map state consumers (reference check)

**Wave 2: Shared Math + Adapters** (3 tasks, depends on Wave 1)
- Task 4: Shared `align_world_to_axis_directions()` helper (SVD, orthogonalization, transform delegation)
- Task 5: Mode-specific triangulation adapters (pinhole N-view, refractive ray-based)
- Task 6: CSV loader + UI button wiring

**Wave 3: Integration** (2 tasks, depends on Wave 2)
- Task 7: Hook into pinhole completion (`_on_calibration_finished`)
- Task 8: Hook into refractive completion (`_on_refractive_finished`)

**Wave 4: Verification** (2 tasks, depends on Wave 3)
- Task 9: Viewer state coherence audit
- Task 10: Full regression suite + evidence capture

**Total**: 10 tasks across 4 waves; total critical path ≈4–5 hours for focused implementation agent.

### Dependency Matrix

```
Task 1 (Bug fix) ──┐
                   ├─→ Task 4 (Shared helper) ──┐
Task 2 (Scaffold)─┤                             ├─→ Task 7 (Pinhole hook)
                  │                             │
Task 3 (Map)  ────┤   Task 5 (Adapters) ───────┤   Task 9 (Coherence)
                  │                             │
                  └─→ Task 6 (CSV loader) ──────┼────────────────────┐
                                                │                    ├─→ Task 10 (Full regression)
                                         Task 8 (Refractive hook) ───┘
```

### Agent Dispatch Summary

| Wave | Tasks | Count | Categories | Notes |
|------|-------|-------|------------|-------|
| 1 | 1,2,3 | 3 | `deep`, `deep`, `quick` | Parallel; establish test baseline |
| 2 | 4,5,6 | 3 | `deep`, `deep`, `quick` | Parallel; core math + UI |
| 3 | 7,8 | 2 | `deep`, `deep` | Sequential or quick parallel |
| 4 | 9,10 | 2 | `unspecified-high`, `unspecified-high` | Parallel; final validation |

## TODOs

### Wave 1: Prerequisite + Scaffold

- [x] **1. Fix pinhole finalization state-frame bug**

  **What to do**:
  - Read `WandCalibrator._finalize_calibration` (wand_calibrator.py:2635–2786)
  - Understand centroid recentering logic (lines 2683–2691)
  - Identify where `_parse_results(res.x, ...)` is called (line ~2777)
  - **Issue**: Local `cam_params` are shifted; raw `res.x` is not → frame mismatch
  - **Fix**: Reconstruct shifted `res.x` from recentered `cam_params` before `_parse_results` call
  - Approach: Build `params_consistent` by copying `res.x` and overwriting camera slice with recentered `cam_params.reshape(-1)`
  - Verify: Ensure `final_params` and `points_3d` both in same (recentered) world frame post-finalization
  - Create unit test `test_axis_alignment.py::test_pinhole_finalize_consistency` to validate

  **Must NOT do**: Alter centroid logic, optimization result object, metric computation; only fix the state-handoff path

  **Recommended Agent Profile**:
  - Category: `deep` — Requires reading complex optimizer state, understanding frame semantics, careful surgical edit
  - Skills: `["git-master"]` — Will commit fix and test
  - Omitted: None essential; `git-master` sufficient

  **Parallelization**: Can Parallel: NO (prerequisite blocks Tasks 4,7,8) | Wave: 1 | Blocks: 4,7,8 | Blocked By: None

  **References**:
  - File: `modules/camera_calibration/wand_calibration/wand_calibrator.py:2635–2786` (finalization logic)
  - File: `modules/camera_calibration/wand_calibration/wand_calibrator.py:3135–3179` (`_parse_results` storage)
  - Pattern: Existing centroid logic at lines 2683–2691
  - Test precedent: `.sisyphus/test_bootstrap_v2.py` (lines 53–216, synthetic setup + metrics)

  **Acceptance Criteria** (agent-executable only):
  - [ ] Read `_finalize_calibration` method; confirm centroid shift at lines 2683–2691
  - [ ] Confirm `_parse_results` called with raw `res.x` at line ~2777
  - [ ] Implement `params_consistent = res.x.copy(); params_consistent[:n_cam_params_total] = cam_params.reshape(-1)`
  - [ ] Modify line ~2777 to call `self._parse_results(params_consistent, cam_id_map)`
  - [ ] py_compile `wand_calibrator.py` — zero syntax errors
  - [ ] Create `tests/test_axis_alignment.py` with `test_pinhole_finalize_consistency` fixture
  - [ ] Test: Mock simple 2-camera pinhole; call `_finalize_calibration`; verify `final_params` and `points_3d` in same frame
  - [ ] Test assertions: centroid ≈ 0, no NaNs, camera centers consistent, reprojection within tolerance
  - [ ] Run: `pytest tests/test_axis_alignment.py::test_pinhole_finalize_consistency -v`
  - [ ] Commit: `fix(calibration): ensure pinhole final state uses consistent world frame`

  **QA Scenarios**:
  ```
  Scenario: Happy Path — Finalization Produces Consistent State
    Tool: bash
    Steps:
      1. Run: `cd modules/camera_calibration/wand_calibration && python -m py_compile wand_calibrator.py`
      2. Run: `pytest tests/test_axis_alignment.py::test_pinhole_finalize_consistency -v`
    Expected: Both pass (no syntax errors, test assertions pass)
    Evidence: `.sisyphus/evidence/task-1-finalize-fix-tests.txt` (pytest output)

  Scenario: Verify Centroid Logic Preserved
    Tool: bash
    Steps:
      1. Read test fixture centroid before/after fix
      2. Assert: centroid after finalization ≈ [0, 0, 0]
      3. Assert: np.allclose(centroid_before, centroid_after, atol=1e-10)
    Expected: Centroid behavior unchanged; only camera-frame consistency fixed
    Evidence: `.sisyphus/evidence/task-1-centroid-preservation.txt` (metric output)
  ```

  **Commit**: YES | Message: `fix(calibration): ensure pinhole final state uses consistent world frame` | Files: `wand_calibrator.py`, `tests/test_axis_alignment.py`

---

- [x] **2. Create test scaffold + validation baseline**

  **What to do**:
  - Design synthetic 2-camera + N-point pinhole/refractive test setup (reuse `.sisyphus/test_bootstrap_v2.py` pattern)
  - Create test utility module `tests/test_utils_axis_alignment.py` with:
    - `generate_synthetic_pinhole_setup(num_cams=2, num_points=4)` → intrinsics, extrinsics, 3D points
    - `project_points(K, R, T, points_3d)` → 2D observations with optional noise
    - `triangulate_synthetic_landmarks(obs_by_cam, K, R_list, T_list)` → reconstructed 3D
    - `compute_orthogonality_metrics(R)` → ||R.T@R - I||, det(R), singular values
    - `compute_reprojection_error(points_3d, obs, K, R, T)` → RMS pixel error
  - Define acceptance thresholds for axis-alignment validation:
    - Orthogonality: `||R.T@R - I|| ≤ 1e-10`
    - Determinant: `|det(R) - 1| ≤ 1e-10`
    - Reprojection: RMS error increase ≤ 0.1 pixels (or preserve ±10%)
    - Centroid: `||mean(points_3d)|| ≤ 1e-8`
  - Create baseline test file `tests/test_axis_alignment_baseline.py` with:
    - `test_synthetic_pinhole_setup` — confirms synthetic data generation works
    - `test_orthogonality_metrics` — verifies metric computation
    - `test_reprojection_baseline` — establishes pre-alignment accuracy

  **Must NOT do**: Add actual axis-alignment logic; only scaffold and metrics

  **Recommended Agent Profile**:
  - Category: `deep` — Requires numeric test design, metric formulation, fixture construction
  - Skills: None essential; standard numpy/scipy/cv2 suffice
  - Omitted: None

  **Parallelization**: Can Parallel: YES (independent of Task 1) | Wave: 1 | Blocks: 4,5,6,9,10 | Blocked By: None

  **References**:
  - Pattern: `.sisyphus/test_bootstrap_v2.py:53–216` (synthetic setup + projections + metrics)
  - Pattern: `.sisyphus/diag_scale.py:103–145` (pose recovery + triangulation)
  - API: cv2.triangulatePoints, cv2.Rodrigues, numpy.linalg.svd
  - Standard thresholds: 1e-10 for orthogonality/determinant (double-precision limits)

  **Acceptance Criteria** (agent-executable only):
  - [ ] Create `tests/test_utils_axis_alignment.py` with 5+ utility functions
  - [ ] Create `tests/test_axis_alignment_baseline.py` with 3 baseline tests
  - [ ] Run: `pytest tests/test_axis_alignment_baseline.py -v`
  - [ ] All 3 tests pass
  - [ ] Verify orthogonality metric ≈ 0 for identity R, >> 0 for random matrix
  - [ ] Verify reprojection error computation within ±1e-2 pixels of manual cv2.projectPoints
  - [ ] Document acceptance thresholds in test file header

  **QA Scenarios**:
  ```
  Scenario: Synthetic Data Generation Works
    Tool: bash
    Steps:
      1. Run: `pytest tests/test_axis_alignment_baseline.py::test_synthetic_pinhole_setup -v`
    Expected: Test passes; 2 cameras, 4 points with consistent observations
    Evidence: `.sisyphus/evidence/task-2-synthetic-setup.txt` (pytest output)

  Scenario: Metrics Behave Correctly
    Tool: bash
    Steps:
      1. Run: `pytest tests/test_axis_alignment_baseline.py::test_orthogonality_metrics -v`
    Expected: Identity R → metric ≈ 0; random R → metric >> 0
    Evidence: `.sisyphus/evidence/task-2-orthogonality-metrics.txt` (pytest output)
  ```

  **Commit**: YES | Message: `test: add axis-alignment test scaffold and validation utilities` | Files: `tests/test_utils_axis_alignment.py`, `tests/test_axis_alignment_baseline.py`

---

- [x] **3. Map axis-direction-map state consumers**

  **What to do**:
  - Search for all usages of `axis_direction_map` in codebase via grep/LSP
  - Search for all usages of `_save_axis_data` and where it's called
  - Search for downstream consumers that read axis-point CSV
  - Document: (a) where it's defined, (b) where it's populated, (c) where it's saved, (d) where it's loaded/used
  - Expected findings (from prior exploration): Currently only computed/saved; no consumers yet
  - Confirm: New axis-alignment helper will be the FIRST downstream consumer

  **Must NOT do**: Modify any consumer code; read-only audit

  **Recommended Agent Profile**:
  - Category: `quick` — Simple grep/search, reference audit, no logic changes
  - Skills: None essential
  - Omitted: None

  **Parallelization**: Can Parallel: YES (independent of Task 1) | Wave: 1 | Blocks: None | Blocked By: None

  **References**:
  - File: `modules/camera_calibration/view.py:3168–3229` (`_save_axis_data`)
  - Search term: `axis_direction_map` (should find only definition + save site currently)
  - Search term: `_save_axis_data` (should find only call site in UI)

  **Acceptance Criteria** (agent-executable only):
  - [ ] Use grep to find all `axis_direction_map` references in Python files
  - [ ] Use grep to find all `_save_axis_data` references
  - [ ] Use grep to find all CSV axis-point file loads (should be zero currently)
  - [ ] Report: (a) definition location, (b) where populated (axis detection UI), (c) where saved (_save_axis_data), (d) no current downstream readers
  - [ ] Confirm schema: `{cam_idx: {"center":[x,y], "+X":[x,y], "+Y":[x,y], "+Z":[x,y]}}`

  **QA Scenarios**:
  ```
  Scenario: All References Located
    Tool: bash
    Steps:
      1. Run: `grep -r "axis_direction_map" . --include="*.py" | head -20`
      2. Run: `grep -r "_save_axis_data" . --include="*.py"`
    Expected: Find ~4–6 references to axis_direction_map; ~2 to _save_axis_data; zero CSV loaders
    Evidence: `.sisyphus/evidence/task-3-reference-audit.txt` (grep output)
  ```

  **Commit**: NO (read-only audit)

---

### Wave 2: Shared Math + Adapters

- [x] **4. Shared `align_world_to_axis_directions()` helper**

  **What to do**:
  - Create new function in `modules/camera_calibration/wand_calibration/refractive_geometry.py`
  - Function signature:
    ```python
    def align_world_to_axis_directions(
        axis_direction_map,      # {cam_idx: {"center":[x,y], "+X":[x,y], "+Y":[x,y], "+Z":[x,y]}}
        triangulate_fn,          # callable(landmark_obs_dict) → (points_3d, validity_flags)
        cam_params,              # camera parameters dict/array
        points_3d,               # existing 3D points to transform
        window_planes=None,      # optional refraction planes {wid: {...}}
        validate_coverage=True   # require 2+ cameras per landmark
    ) → (success, R_world, t_shift, transformed_state_dict)
    ```
  - Implementation logic:
    1. Call `triangulate_fn` for each landmark (center, +X, +Y, +Z) → 4 × 3D point sets
    2. Validate: Each landmark has 2+ cameras; all points finite/not behind cameras
    3. Compute direction vectors: `dir_X = points_3d["+X"] - points_3d["center"]` (similarly for Y, Z)
    4. Normalize: `dir_X /= ||dir_X||` (similarly for Y, Z)
    5. Construct 3×3 matrix `M = [dir_X | dir_Y | dir_Z]`
    6. SVD: `U, S, Vt = np.linalg.svd(M)`
    7. Orthogonal basis: `R_new = U @ Vt` (closest orthonormal to M in Frobenius norm)
    8. Verify: `det(R_new) > 0` (if negative, flip sign to ensure right-handed)
    9. Translation: `t_shift = -points_3d["center"]` (shift world origin to axis center)
    10. Delegate rigid transform to existing `apply_coordinate_rotation(R_new, t_shift, ...)`
    11. Return: (success, R_new, t_shift, transformed dict with `cam_params`, `points_3d`, `window_planes`)
  - Error handling:
    - If triangulation fails for any landmark → return (False, None, None, None); caller must revert
    - If SVD singular/ill-conditioned (cond number > 1e12) → return failure
    - If det(R) « 0 (reflection detected) → return failure
  - Logging: Emit debug messages for each triangulation, SVD metrics (singular values, condition number)

  **Must NOT do**: Apply transform in-place; only compute and return it; let caller decide whether to commit

  **Recommended Agent Profile**:
  - Category: `deep` — SVD mathematics, rigid transform semantics, numerical validation
  - Skills: None essential; numpy/scipy suffice
  - Omitted: None

  **Parallelization**: Can Parallel: NO (depends on Task 1 bug fix; Task 5 adapters needed too) | Wave: 2 | Blocks: 7,8 | Blocked By: 1

  **References**:
  - File: `modules/camera_calibration/wand_calibration/refractive_geometry.py:624–709` (apply_coordinate_rotation signature/behavior)
  - Algorithm: SVD polar decomposition (standard; reference: "Procrustes problem" in linear algebra)
  - Validation: Singular value ratios, condition number checks (numerical recipes)
  - Test: `.sisyphus/test_bootstrap_v2.py:130–216` (reprojection validation pattern)

  **Acceptance Criteria** (agent-executable only):
  - [ ] Function created in `refractive_geometry.py`
  - [ ] Accepts `axis_direction_map` and `triangulate_fn` callable
  - [ ] Returns (success, R_world, t_shift, transformed_dict)
  - [ ] Calls triangulate_fn for each landmark; validates coverage
  - [ ] Computes SVD polar decomposition correctly
  - [ ] Verifies `det(R) ≈ +1` and `||R.T@R - I|| ≈ 0` within 1e-10
  - [ ] Delegates rigid transform to `apply_coordinate_rotation`
  - [ ] All-or-nothing failure: if any landmark fails, returns (False, ...)
  - [ ] Unit test: test with synthetic 2-camera, 4-point setup; verify output R, t satisfy constraints

  **QA Scenarios**:
  ```
  Scenario: Happy Path — Axis Alignment Succeeds
    Tool: bash
    Steps:
      1. Create synthetic pinhole setup (Task 2 utils)
      2. Call align_world_to_axis_directions with valid landmarks
      3. Check: success=True, R satisfies constraints, t = -axis_center
    Expected: Alignment computes successfully; orthogonality metrics pass
    Evidence: `.sisyphus/evidence/task-4-alignment-happy-path.txt` (test output + metrics)

  Scenario: Failure Case — Insufficient Camera Coverage
    Tool: bash
    Steps:
      1. Create setup with +X landmark visible in only 1 camera
      2. Call align_world_to_axis_directions with validate_coverage=True
      3. Check: success=False, returns None for R, t
    Expected: Function rejects insufficient coverage; returns failure gracefully
    Evidence: `.sisyphus/evidence/task-4-alignment-coverage-fail.txt` (error message)
  ```

  **Commit**: YES | Message: `feat(calibration): add shared world-axis alignment helper with SVD orthogonalization` | Files: `refractive_geometry.py`

---

- [x] **5. Mode-specific triangulation adapters**

  **What to do**:
  - Create two adapter functions in `refractive_geometry.py`:
    1. `triangulate_pinhole_landmarks(obs_dict, cam_params_dict, cam_id_map)`
       - Takes axis observations (cam_idx → {center:[x,y], +X:[x,y], ...})
       - Uses `_triangulate_frame` pattern from wand_calibrator (N-view SVD)
       - Returns (points_3d_dict, validity_flags) where:
         - `points_3d_dict = {"center": [x,y,z], "+X": [...], "+Y": [...], "+Z": [...]}`
         - `validity_flags = {landmark: (num_cameras, success_flag)}`
    2. `triangulate_refractive_landmarks(obs_dict, cam_params_dict, window_planes, cam_to_window, media)`
       - Uses `build_pinplate_rays_cpp_batch` + `triangulate_point` pattern
       - Returns same shape as pinhole adapter
  - These adapters bridge axis-point observations to the SVD helper
  - Adapters handle mode-specific details (ray building, ray intersection) transparently

  **Must NOT do**: Modify core `_triangulate_frame` or `triangulate_point`; create wrappers only

  **Recommended Agent Profile**:
  - Category: `deep` — Requires understanding pinhole N-view SVD and refractive ray-based geometry
  - Skills: None essential
  - Omitted: None

  **Parallelization**: Can Parallel: YES (independent of Task 4, but both feed Task 7,8) | Wave: 2 | Blocks: 7,8 | Blocked By: 1,2

  **References**:
  - File: `modules/camera_calibration/wand_calibration/wand_calibrator.py:2867–2937` (`_triangulate_frame` — pinhole pattern)
  - File: `modules/camera_calibration/wand_calibration/refractive_geometry.py:229–389` (ray-building + triangulation — refractive pattern)
  - File: `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:1384–1822` (refractive dataset example)

  **Acceptance Criteria** (agent-executable only):
  - [ ] `triangulate_pinhole_landmarks` created in `refractive_geometry.py`
  - [ ] Takes 2D observations per camera, calls N-view SVD (from wand_calibrator pattern)
  - [ ] Returns (points_3d_dict, validity_flags)
  - [ ] `triangulate_refractive_landmarks` created in `refractive_geometry.py`
  - [ ] Takes 2D observations, builds refracted rays, calls `triangulate_point` per landmark
  - [ ] Returns same shape as pinhole adapter
  - [ ] Unit test: Mock 2-camera pinhole landmarks; call both adapters; verify shape/finiteness

  **QA Scenarios**:
  ```
  Scenario: Pinhole Adapter — Happy Path
    Tool: bash
    Steps:
      1. Synthetic 2-camera setup with 4 landmarks (center, +X, +Y, +Z)
      2. Call triangulate_pinhole_landmarks with synthetic observations
      3. Verify: returns dict with 4 keys, each 3×1 array
    Expected: Landmarks triangulated successfully
    Evidence: `.sisyphus/evidence/task-5-pinhole-adapter-happy.txt`

  Scenario: Refractive Adapter — Happy Path
    Tool: bash
    Steps:
      1. Synthetic 2-camera refractive setup
      2. Call triangulate_refractive_landmarks with ray parameters
      3. Verify: returns dict with 4 keys, ray-based triangulation results
    Expected: Landmarks triangulated via ray intersection
    Evidence: `.sisyphus/evidence/task-5-refractive-adapter-happy.txt`
  ```

  **Commit**: YES | Message: `feat(calibration): add mode-specific triangulation adapters for axis landmarks` | Files: `refractive_geometry.py`

---

- [x] **6. CSV loader + UI button wiring**

  **What to do**:
  - Create CSV loader function in `modules/camera_calibration/view.py`:
    ```python
    def _load_axis_points_csv(self, file_path):
        """Load 9-column axis-direction CSV and populate self.axis_direction_map"""
        # Read CSV with pandas or csv.reader
        # Schema: cam_id, center_x, center_y, plus_x_x, plus_x_y, plus_y_x, plus_y_y, plus_z_x, plus_z_y
        # Populate: self.axis_direction_map = {cam_idx: {"center":[x,y], "+X":[x,y], "+Y":[x,y], "+Z":[x,y]}}
        # Auto-switch: self.ui.axis_mode_combo.setCurrentIndex(CUSTOM_AXIS_MODE_INDEX)
        # Signal: self.axis_data_loaded_signal.emit()
    ```
  - Add "Load Axis Points" button in UI (view.py line ~1553, below "Load Wand Points")
    - Button visibility: Show only if `axis_direction_map` is non-empty OR user explicitly clicks it
    - Button state: Enabled after calibration; disabled during/after alignment
  - Wire button to `_load_axis_points_csv` via file dialog
  - Add validation: Check CSV has 9 columns, parseable floats, camera IDs match calibrator

  **Must NOT do**: Modify existing axis-detection UI; only add CSV loader entry point

  **Recommended Agent Profile**:
  - Category: `quick` — File I/O, CSV parsing, UI wiring (straightforward)
  - Skills: None essential; PySide6 + pandas/csv standard
  - Omitted: None

  **Parallelization**: Can Parallel: YES (independent of Tasks 4,5) | Wave: 2 | Blocks: 7,8,9 | Blocked By: 1,2

  **References**:
  - File: `modules/camera_calibration/view.py:3168–3229` (`_save_axis_data` — CSV format reference)
  - File: `modules/camera_calibration/view.py:1553` (button placement target)
  - File: `modules/camera_calibration/view.py:3188` (`axis_direction_map` schema)
  - UI pattern: `_load_wand_points_for_calibration` (line 1553) — similar file dialog

  **Acceptance Criteria** (agent-executable only):
  - [ ] Function `_load_axis_points_csv` created in view.py
  - [ ] Reads 9-column CSV (cam_id, center_x, center_y, ...)
  - [ ] Populates `self.axis_direction_map` with correct schema
  - [ ] Auto-switches axis mode to Custom if CSV loaded successfully
  - [ ] "Load Axis Points (Optional)" button added below "Load Wand Points" (line ~1553)
  - [ ] Button calls file dialog → `_load_axis_points_csv`
  - [ ] Button disabled during/after alignment (sets enablement state)
  - [ ] Unit test: Create test CSV, call loader, verify `axis_direction_map` populated correctly

  **QA Scenarios**:
  ```
  Scenario: CSV Load Happy Path
    Tool: bash
    Steps:
      1. Create test CSV with 2 cameras, 9 columns of known data
      2. Call _load_axis_points_csv(test_csv_path)
      3. Verify: self.axis_direction_map populated; axis mode set to Custom
    Expected: CSV loaded successfully; UI state updated
    Evidence: `.sisyphus/evidence/task-6-csv-loader-happy.txt`

  Scenario: CSV Load Error — Malformed File
    Tool: bash
    Steps:
      1. Create malformed CSV (missing column, non-float data)
      2. Call _load_axis_points_csv(bad_csv_path)
      3. Verify: Error message shown; axis_direction_map unchanged
    Expected: Graceful error handling
    Evidence: `.sisyphus/evidence/task-6-csv-loader-error.txt`
  ```

  **Commit**: YES | Message: `feat(ui): add Load Axis Points CSV button and loader function` | Files: `view.py`

---

### Wave 3: Integration

- [x] **7. Hook into pinhole completion (`_on_calibration_finished`)**

  **What to do**:
  - Locate: `modules/camera_calibration/view.py:5232` (pinhole completion callback)
  - After calibration finalization, add conditional alignment trigger:
    ```python
    if self.axis_direction_map:  # if axis points exist
        # Triangulate axis landmarks using pinhole adapter
        # Call align_world_to_axis_directions
        # If success: update self.wand_calibrator.final_params, .points_3d
        # If failure: log error, keep original state
        # Refresh: self._update_3d_viz()
    ```
  - Error handling:
    - If triangulation fails → log warning, skip alignment, proceed with original calibration
    - If orthogonalization fails → log warning, skip alignment
    - If transform application fails → log error, skip alignment
  - Logging: Emit detailed debug messages showing triangulation residuals, SVD singular values, alignment metrics
  - Re-render: Call `self._update_3d_viz()` to display aligned state

  **Must NOT do**: Alter pinhole finalization logic; only add post-finalization alignment hook

  **Recommended Agent Profile**:
  - Category: `deep` — Requires understanding calibration state flow, conditional alignment logic, error recovery
  - Skills: None essential
  - Omitted: None

  **Parallelization**: Can Parallel: NO (sequential integration; Task 8 independent) | Wave: 3 | Blocks: 9 | Blocked By: 1,4,5,6

  **References**:
  - Hook point: `modules/camera_calibration/view.py:5232–5280` (`_on_calibration_finished`)
  - Adapter: Task 5 (`triangulate_pinhole_landmarks`)
  - Helper: Task 4 (`align_world_to_axis_directions`)
  - Viewer: `_update_3d_viz` (line 5281)

  **Acceptance Criteria** (agent-executable only):
  - [ ] Locate `_on_calibration_finished` at line 5232
  - [ ] Add conditional alignment block: `if self.axis_direction_map: align_world_to_axis_directions(...)`
  - [ ] Use `triangulate_pinhole_landmarks` adapter for pinhole mode
  - [ ] Call shared `align_world_to_axis_directions` helper
  - [ ] If success: Update `self.wand_calibrator.final_params` and `.points_3d` with transformed values
  - [ ] If failure: Log warning; keep original state
  - [ ] Call `self._update_3d_viz()` to refresh 3D viewer
  - [ ] Unit test: Mock calibrator + axis_direction_map; call _on_calibration_finished; verify alignment applied or skipped correctly

  **QA Scenarios**:
  ```
  Scenario: Pinhole Alignment Happy Path
    Tool: bash
    Steps:
      1. Mock calibration completion with axis_direction_map populated
      2. Call _on_calibration_finished(success=True, ...)
      3. Verify: Alignment triggered; final_params/points_3d transformed
      4. Verify: 3D viewer re-rendered with aligned state
    Expected: Alignment applied successfully; state consistent
    Evidence: `.sisyphus/evidence/task-7-pinhole-alignment-success.txt`

  Scenario: Pinhole Alignment Skipped (No Axis Data)
    Tool: bash
    Steps:
      1. Mock calibration completion with empty axis_direction_map
      2. Call _on_calibration_finished
      3. Verify: No alignment triggered; original state preserved
    Expected: Graceful skip; calibration state unchanged
    Evidence: `.sisyphus/evidence/task-7-pinhole-alignment-skip.txt`
  ```

  **Commit**: YES | Message: `feat(integration): add post-calibration axis alignment hook for pinhole mode` | Files: `view.py`

---

- [x] **8. Hook into refractive completion (`_on_refractive_finished`)**

  **What to do**:
  - Locate: `modules/camera_calibration/view.py:7480` (refractive completion callback)
  - After refractive calibration finalization, add conditional alignment trigger (similar to Task 7):
    ```python
    if self.axis_direction_map:
        # Triangulate axis landmarks using refractive adapter
        # Call align_world_to_axis_directions
        # If success: update cam_params, window_planes, points_3d from returned dict
        # If failure: log error, keep original state
        # Refresh: self.calib_3d_view.plot_refractive(...)
    ```
  - Refractive-specific: Also transform `window_planes` (via `apply_coordinate_rotation`)
  - Error handling: Same as Task 7 (all-or-nothing, log, skip on failure)
  - Logging: Show triangulation residuals, ray intersection metrics, alignment metrics
  - Re-render: Call `self.calib_3d_view.plot_refractive(cam_params, window_planes, points_3d)`

  **Must NOT do**: Alter refractive finalization logic; only add post-finalization alignment hook

  **Recommended Agent Profile**:
  - Category: `deep` — Similar complexity to Task 7; refractive-specific window plane handling
  - Skills: None essential
  - Omitted: None

  **Parallelization**: Can Parallel: YES (Task 7 pinhole, Task 8 refractive independent) | Wave: 3 | Blocks: 9 | Blocked By: 1,4,5,6

  **References**:
  - Hook point: `modules/camera_calibration/view.py:7480–7566` (`_on_refractive_finished`)
  - Adapter: Task 5 (`triangulate_refractive_landmarks`)
  - Helper: Task 4 (`align_world_to_axis_directions`)
  - Viewer: Line 7563–7566 (plot_refractive call)
  - Window planes: `window_planes[wid] = {"plane_pt", "plane_n", "thick_mm"}`

  **Acceptance Criteria** (agent-executable only):
  - [ ] Locate `_on_refractive_finished` at line 7480
  - [ ] Add conditional alignment block: `if self.axis_direction_map: align_world_to_axis_directions(...)`
  - [ ] Use `triangulate_refractive_landmarks` adapter for refractive mode
  - [ ] Call shared `align_world_to_axis_directions` helper
  - [ ] If success: Update `cam_params`, `window_planes`, `points_3d` with transformed values
  - [ ] If failure: Log warning; keep original state
  - [ ] Call `self.calib_3d_view.plot_refractive(cam_params, window_planes, points_3d)`
  - [ ] Unit test: Mock refractive calibrator + axis_direction_map; call _on_refractive_finished; verify alignment applied or skipped correctly

  **QA Scenarios**:
  ```
  Scenario: Refractive Alignment Happy Path
    Tool: bash
    Steps:
      1. Mock refractive calibration completion with axis_direction_map populated
      2. Call _on_refractive_finished(success=True, cam_params, report, dataset)
      3. Verify: Alignment triggered; cam_params, window_planes, points_3d transformed
      4. Verify: 3D viewer re-rendered with aligned state
    Expected: Alignment applied successfully; all state updated atomically
    Evidence: `.sisyphus/evidence/task-8-refractive-alignment-success.txt`

  Scenario: Refractive Alignment Skipped (No Axis Data)
    Tool: bash
    Steps:
      1. Mock refractive calibration with empty axis_direction_map
      2. Call _on_refractive_finished
      3. Verify: No alignment triggered; original state preserved
    Expected: Graceful skip; calibration state unchanged
    Evidence: `.sisyphus/evidence/task-8-refractive-alignment-skip.txt`
  ```

  **Commit**: YES | Message: `feat(integration): add post-calibration axis alignment hook for refractive mode` | Files: `view.py`

---

### Wave 4: Verification

- [x] **9. Viewer state coherence audit**

  **What to do**:
  - After alignment hooks added (Tasks 7,8), audit the 3D viewer and UI state for stale/inconsistent references:
    - [ ] Wand-length display: Uses `self.wand_calibrator.points_3d` → verify it reflects aligned state
    - [ ] Residual visualization: Uses `self.wand_calibrator.per_frame_errors` → document that these refer to PRE-alignment metrics (acceptable; document in tooltip)
    - [ ] Camera matrix display in UI: Should show transformed `final_params` → verify
    - [ ] Axis direction overlays on 3D viewer: Should show axis landmarks post-alignment → verify
    - [ ] Refractive plate display: Should show transformed planes → verify
  - Identify any cached metrics/displays that reference pre-alignment state
  - Document which are acceptable (e.g., optimization residuals) and which need refresh
  - Add comments to relevant UI code noting alignment-induced state changes

  **Must NOT do**: Modify core calibration logic; only audit and document

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Code review, state coherence analysis, documentation
  - Skills: None essential
  - Omitted: None

  **Parallelization**: Can Parallel: YES (independent audit; Task 10 can run in parallel) | Wave: 4 | Blocks: None | Blocked By: 7,8

  **References**:
  - Viewer methods: `plot_calibration`, `plot_refractive` (view.py:590–907)
  - Wand-length display: Search for wand-length references in view.py
  - Residual display: Search for per_frame_errors references
  - UI state updates: `_update_3d_viz` (line 5281)

  **Acceptance Criteria** (agent-executable only):
  - [ ] Audit all uses of `self.wand_calibrator.points_3d` post-alignment → verify reflects transformed points
  - [ ] Audit all uses of `self.wand_calibrator.per_frame_errors` → document as pre-alignment metrics
  - [ ] Audit axis-direction display → verify shows landmarks post-alignment
  - [ ] Audit window-plane display (refractive) → verify shows transformed planes
  - [ ] Add comments to relevant UI code (1–2 sentence each) documenting alignment-induced state changes
  - [ ] Run pylint/flake8 on modified files → zero errors

  **QA Scenarios**:
  ```
  Scenario: Viewer State Coherence Check
    Tool: bash
    Steps:
      1. Perform alignment in UI (if interactive test possible)
      2. Verify: 3D viewer shows aligned cameras/points
      3. Verify: Wand-length display reflects transformed state
      4. Check UI tooltips/docs for notes on stale residuals
    Expected: All viewer elements consistent with aligned state (except documented stale metrics)
    Evidence: `.sisyphus/evidence/task-9-viewer-coherence.txt` (audit checklist + screenshots if GUI)
  ```

  **Commit**: YES | Message: `docs(ui): audit and document viewer state coherence post-alignment` | Files: `view.py` (comments added)

---

- [x] **10. Full regression suite + evidence capture**

  **What to do**:
  - Run comprehensive validation:
    1. **py_compile check**: Verify all modified Python files compile without syntax errors
       - `python -m py_compile wand_calibrator.py refractive_geometry.py view.py tests/test_axis_alignment.py`
    2. **Test bootstrap**: Run existing `.sisyphus/test_bootstrap_v2.py` to ensure no regressions in core calibration
       - Should pass with same thresholds as before
    3. **Axis alignment unit tests**: Run Task 2 baseline tests + Task 4–8 feature tests
       - `pytest tests/test_axis_alignment*.py -v --tb=short`
    4. **Integration test**: Synthetic end-to-end (mock calibration → load axis → align → verify state)
       - Create mini e2e test script that orchestrates full flow
    5. **Evidence capture**: For each test, save output to `.sisyphus/evidence/task-10-{category}-{timestamp}.txt`

  **Must NOT do**: Modify source code; only run validation scripts

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Test orchestration, regression validation, evidence collection
  - Skills: None essential; bash + pytest standard
  - Omitted: None

  **Parallelization**: Can Parallel: YES (all tests independent; can run in parallel) | Wave: 4 | Blocks: None | Blocked By: 1–9

  **References**:
  - Pattern: `.sisyphus/test_bootstrap_v2.py` (existing test precedent)
  - Tests: All created in Tasks 1–8 (py_compile, pytest, script-based validation)

  **Acceptance Criteria** (agent-executable only):
  - [ ] Run py_compile on all modified .py files → zero syntax errors
  - [ ] Run existing test_bootstrap_v2.py → passes with same thresholds
  - [ ] Run pytest tests/test_axis_alignment*.py -v → all tests pass
  - [ ] Create e2e integration test script; run → demonstrates full axis-alignment workflow
  - [ ] Capture evidence for each category:
      - `.sisyphus/evidence/task-10-py-compile.txt`
      - `.sisyphus/evidence/task-10-bootstrap-regression.txt`
      - `.sisyphus/evidence/task-10-axis-alignment-unit-tests.txt`
      - `.sisyphus/evidence/task-10-e2e-integration.txt`
  - [ ] Verify all evidence files present and non-empty

  **QA Scenarios**:
  ```
  Scenario: Full Regression Suite
    Tool: bash
    Steps:
      1. Run: `python -m py_compile *.py tests/test_axis_alignment*.py`
      2. Run: `.sisyphus/test_bootstrap_v2.py --threshold 0.5` (or existing invocation)
      3. Run: `pytest tests/test_axis_alignment*.py -v`
      4. Run: custom e2e test script
    Expected: All pass; evidence captured
    Evidence: `.sisyphus/evidence/task-10-full-regression.txt` (combined output)
  ```

  **Commit**: NO (validation only; commits already done in prior tasks)

---

## Final Verification Wave (MANDATORY)

After all 10 tasks complete, **4 review agents run in PARALLEL**. ALL must APPROVE.

- [x] **F1. Plan Compliance Audit** (oracle)
  - Verify: All requirements from user request addressed
  - Verify: All TODOs completed with acceptance criteria met
  - Verify: No scope creep; features match "Must Have" list
  - Verify: Guardrails from Metis incorporated
  - Report: Pass/Fail with summary

- [x] **F2. Code Quality Review** (unspecified-high)
  - Verify: No syntax errors; py_compile passes
  - Verify: Naming conventions consistent with codebase
  - Verify: Docstrings/comments adequate
  - Verify: Error handling complete (no silent failures)
  - Report: Pass/Fail with issues list

- [x] **F3. Real Manual QA** (unspecified-high + playwright if UI interactive)
  - Verify: CSV loader works with sample file
  - Verify: "Load Axis Points" button appears + functions correctly
  - Verify: Alignment trigger fires post-calibration
  - Verify: 3D viewer re-renders with aligned state
  - Verify: No GUI crashes; error messages clear
  - Report: Pass/Fail with test summary

- [x] **F4. Scope Fidelity Check** (deep)
  - Verify: All "Must Have" requirements met
  - Verify: All "Must NOT Have" guardrails respected
  - Verify: No unintended side effects to existing calibration
  - Verify: Test coverage adequate (script-based validation strategy followed)
  - Report: Pass/Fail with deviations (if any)

**CRITICAL**: Do NOT mark F1–F4 as checked before getting **user's explicit approval**. Wait for completion notification.

## Commit Strategy

All commits made with `git-master` skill in atomic fashion:
1. Task 1: Bug fix (1 commit)
2. Task 2: Test scaffold (1 commit)
3. Task 4: Shared helper (1 commit)
4. Task 5: Adapters (1 commit)
5. Task 6: CSV loader + UI (1 commit)
6. Task 7: Pinhole hook (1 commit)
7. Task 8: Refractive hook (1 commit)
8. Task 9: State audit + docs (1 commit)

Total: 8 commits, each with clear message and affected files.

## Success Criteria

**Plan is complete when:**
1. All 10 tasks executed with evidence captured
2. All 4 final verification agents pass (F1–F4)
3. User gives explicit approval
4. Evidence artifacts stored in `.sisyphus/evidence/`
5. Draft deleted; plan moved to final state

---

**Plan Generated**: 2026-03-22 22:10 UTC  
**Status**: READY FOR EXECUTION  
**Next Step**: Await user approval; then dispatch Wave 1 executor agents

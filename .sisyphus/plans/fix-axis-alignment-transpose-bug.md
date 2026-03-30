# Fix: Axis Alignment Transpose Bug — Cameras/Points Misaligned After Alignment

## TL;DR
> **Summary**: After axis alignment succeeds, cameras and 3D points appear misaligned in the 3D view because `R_new` at **BOTH lines 812 AND 820** of `refractive_geometry.py` should be `(U @ Vt).T` and `(U_fix @ Vt).T`, not `U @ Vt` and `U_fix @ Vt`. This is a **two-line fix** in the orientation basis construction (same root cause, same function).
> **Deliverables**: Fixed `R_new` computation (both lines), regression test with non-aligned landmarks, test for left-handed triad path, verified 3D view renders correctly aligned cameras/points
> **Effort**: Short
> **Parallel**: NO
> **Critical Path**: Fix lines 812+820 → Add regression tests → Verify 3D view alignment

**⚠️ METIS FINDING**: Line 820 (reflection-fix branch) has the **identical transpose bug**. Current plan only fixed line 812, leaving latent bug in `det < 0` code path.

---

## Context

### Original Issue
User reports: "After clicking 'Precalibrate to Check', the message shows '[Axis Alignment] World coordinate alignment applied successfully', but in the 3D view, the camera and 3D points didn't seem to be aligned to a desired direction."

### Root Cause (Explorer + Metis Findings)
The transformation math in `view.py` (lines 5344-5367) and `refractive_geometry.py` (lines 624-709) are **internally consistent**. No errors there.

The bug is **upstream** at **BOTH lines 812 AND 820** of `refractive_geometry.py`:
- `M = [dir_X dir_Y dir_Z]` contains desired new axes as **columns** in the old frame
- For the transform `X_new = R_world @ (X_old - center)` to map those directions onto canonical axes `[e_x, e_y, e_z]`, we need:
  - `R_world @ dir_X = e_x` → `R_world @ dir_Y = e_y` → `R_world @ dir_Z = e_z`
  - This means `R_world = M^{-1}` (and for orthonormal, `M^{-1} = M.T`)
- Current code (line 812): `R_new = U @ Vt ≈ M` ← **WRONG**
- Current code (line 820, reflection branch): `R_new = U_fix @ Vt ≈ M` ← **ALSO WRONG**
- Correct code: `R_new = (U @ Vt).T ≈ M.T = M^{-1}` and `R_new = (U_fix @ Vt).T` ← **RIGHT**

**Why line 820 was overlooked**: The reflection-correction path (triggered when `det(U @ Vt) < 0`) overwrites `R_new` without transpose. This is unreachable in current tests because all landmarks are canonical-aligned (where M ≈ I, so no reflection needed).

### Technical Detail
SVD: `M = U S V^T`. The polar decomposition gives the closest orthonormal matrix as `U V^T`. But we need the **transpose** of that to invert the direction mapping.

**Metis insight**: `det((U @ Vt).T) = det(U @ Vt)`, so transpose preserves determinant — the det check and reflection logic remain valid regardless of when transpose is applied.

---

## Work Objectives

### Core Objective
Fix the transpose error in `R_new` computation so that axis-aligned landmarks correctly map to world axes, resulting in proper camera and point alignment in the 3D view.

### Deliverables
1. Two-line fix: `R_new = (U @ Vt).T` at line 812 AND `R_new = (U_fix @ Vt).T` at line 820
2. Regression test: non-axis-aligned landmarks (45° rotation case)
3. Regression test: left-handed landmark triad (exercises `det < 0` reflection-fix path)
4. Verified: 3D view renders cameras and points aligned to detected axes

### Definition of Done (verifiable)
- [ ] `refractive_geometry.py` line 812 changed from `R_new = U @ Vt` to `R_new = (U @ Vt).T`
- [ ] `refractive_geometry.py` line 820 changed from `R_new = U_fix @ Vt` to `R_new = (U_fix @ Vt).T`
- [ ] Test file `tests/test_axis_alignment_transpose.py` created with **two** test functions:
  - `test_axis_alignment_non_aligned_landmarks()` — 45° rotated axes
  - `test_axis_alignment_left_handed_triad()` — left-handed system (exercises det<0 path)
- [ ] Both tests pass: `pytest tests/test_axis_alignment_transpose.py -v`
- [ ] 3D view rendering test confirms cameras align to detected axis directions
- [ ] No regressions: all existing axis-alignment tests still pass
- [ ] No bare `U @ Vt` or `U_fix @ Vt` assignments remain (verified via grep regex)
- [ ] Single atomic commit: `fix(geometry): correct R_new transpose in axis alignment basis construction`

### Must Have
- Transpose fix must preserve det(R) = +1 check (already in code at lines 815-825)
- **BOTH line 812 AND line 820 must be transposed** — same root cause, same function, same commit
- Right-handed system enforcement still applies after transpose
- No changes to triangulation or axis-direction detection logic
- New test must directly assert **direction mapping correctness**: `R_world @ dir_X ≈ [1,0,0]` with tolerance 1e-6
- New test must exercise `det < 0` reflection-fix path (left-handed triad case)

### Must NOT Have
- Do NOT modify camera extrinsic application logic (view.py 5355-5357 is correct)
- Do NOT modify point transformation formula (view.py 5366 is correct)
- Do NOT change lines 801-806 (M construction and SVD)
- Do NOT change lines 814-819 (det check logic) — only change assignments on 812 and 820
- Do NOT change `apply_coordinate_rotation` (lines 624-709) — it is correct
- Do NOT change `view.py` downstream consumers — they are correct
- Do NOT remove determinant validation
- Do NOT create criteria requiring "user manually checks 3D view"

---

## Verification Strategy

**Test decision**: Unit tests (no GUI interaction) + manual 3D view check
- Regression test with known non-aligned landmarks
- Verify: after alignment, camera frustums point toward +Z and points form a cube aligned to axes

**QA policy**: Every task has agent-executed scenarios below

---

## Execution Strategy

### Single Wave (Sequential)
1. Fix **both** lines 812 and 820 (same root cause, same function, single commit)
2. Create **two** regression tests (non-aligned + left-handed triad)
3. Run all axis-alignment tests
4. Manual verification of 3D view rendering

### Dependency Matrix
```
1. Fix lines 812 + 820 (two-line fix)
   ↓
2. Add regression tests (both tests use the fixed function)
   ↓
3. Run full test suite (validates fix + no regression)
   ↓
4. Verification: 3D view rendering
```

---

## TODOs

- [ ] 1. Fix transpose in R_new computation at **BOTH lines 812 AND 820**

  **What to do**: 
  - File: `modules/camera_calibration/wand_calibration/refractive_geometry.py`
  - Line 812, change: `R_new = U @ Vt` → `R_new = (U @ Vt).T`
  - Line 820, change: `R_new = U_fix @ Vt` → `R_new = (U_fix @ Vt).T`
  - Both fixes are the same root cause: transposing to invert direction mapping
  - Add inline comment: `# .T inverts M (canonical→detected) to get R (old→new frame)`

  **Must NOT do**: 
  - Do not remove the det(R) check (lines 815-825)
  - Do not touch the M construction (line 802)
  - Do not change the U column flip logic (line 819)
  - Do not touch triangulation
  - Do not change lines in other files (view.py, apply_coordinate_rotation, etc.)

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Two-line fix (same root cause in same function)
  - Skills: [] — Reason: No special skills needed
  - Omitted: — Reason: N/A

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [Task 2] | Blocked By: none

  **References** (executor has NO interview context):
  - Transpose logic: `/D:/0.Code/OpenLPTGUI/OpenLPT/modules/camera_calibration/wand_calibration/refractive_geometry.py:801-825` — SVD basis construction; transpose corrects direction mapping
  - Line 812: `M = [dir_X dir_Y dir_Z]` where `M ≈ U @ Vt` from SVD; need `(U @ Vt).T = M.T = M^{-1}` to invert
  - Line 820: Same logic in reflection-fix path (triggered when `det(U @ Vt) < 0`)
  - Camera convention: `tests/test_utils_axis_alignment.py:33-38` — repo uses `X_cam = R X_world + T`
  - Related transformation code: `refractive_geometry.py:664-675` — uses `R_world.T` correctly in camera extrinsic composition (validates that `R_world` should be `M.T`)

  **Acceptance Criteria** (agent-executable only):
  - [ ] Line 812 reads: `R_new = (U @ Vt).T` (not `U @ Vt`)
  - [ ] Line 820 reads: `R_new = (U_fix @ Vt).T` (not `U_fix @ Vt`)
  - [ ] File saves without syntax errors
  - [ ] No other lines in the function changed (except comment additions)
  - [ ] Regex check confirms: no bare `R_new = U @ Vt` or `R_new = U_fix @ Vt` remain

  **QA Scenarios** (MANDATORY):
  ```
  Scenario: Both transposes applied correctly
    Tool: Bash (grep)
    Steps: rtk grep -n "R_new = (U" modules/camera_calibration/wand_calibration/refractive_geometry.py | grep ".T"
    Expected: Exactly 2 matches (lines 812 and 820, both with .T)
    Evidence: .sisyphus/evidence/task-1-both-transposes.txt

  Scenario: No bare U @ Vt assignments remain
    Tool: Bash (Python regex)
    Steps: conda run -n OpenLPT python -c "import re; f=open('modules/camera_calibration/wand_calibration/refractive_geometry.py').read(); bare=re.findall(r'R_new\s*=\s*U(?:_fix)?\s*@\s*Vt(?!\)\.T)', f, re.MULTILINE); assert len(bare)==0, f'Found un-transposed: {bare}'; print('PASS')"
    Expected: Prints "PASS", exit code 0
    Evidence: .sisyphus/evidence/task-1-no-bare-assignments.txt

  Scenario: No syntax errors introduced
    Tool: Bash (Python compile)
    Steps: conda run -n OpenLPT python -m py_compile modules/camera_calibration/wand_calibration/refractive_geometry.py
    Expected: Exit code 0 (no errors)
    Evidence: .sisyphus/evidence/task-1-syntax-check.txt
  ```

  **Commit**: YES | Message: `fix(geometry): correct R_new transpose in axis alignment basis construction` | Files: `modules/camera_calibration/wand_calibration/refractive_geometry.py`

---

- [ ] 2. Add regression tests for non-aligned and left-handed landmarks

  **What to do**:
  - Create `tests/test_axis_alignment_transpose.py`
  - Implement **two** test functions:
    1. `test_axis_alignment_non_aligned_landmarks()` — Uses 45° rotated axis system (not canonical)
       - Verify that `R_world @ dir_X ≈ [1,0,0]`, `R_world @ dir_Y ≈ [0,1,0]`, `R_world @ dir_Z ≈ [0,0,1]` with tolerance 1e-6
    2. `test_axis_alignment_left_handed_triad()` — Left-handed landmark system that triggers `det < 0` fix
       - Exercise the reflection-correction path (line 820)
       - Verify result still has det=+1 and correct direction mapping (even if one axis is flipped)
  - Follow pattern from `tests/test_axis_alignment.py` (mock triangulation, no pytest fixtures)
  - Use `np.testing.assert_allclose` for direction assertions (exact numeric validation)

  **Must NOT do**:
  - Do not use GUI/Playwright (unit tests only)
  - Do not use pytest fixtures
  - Do not modify existing test files
  - Do not rely on visual inspection (use numeric assertions)

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Template-based tests, <100 lines
  - Skills: [] — Reason: Standard test pattern
  - Omitted: — Reason: N/A

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [Task 3] | Blocked By: [Task 1]

  **References**:
  - Test pattern: `tests/test_axis_alignment.py:1-50` — Use same structure: mock triangulation, lambda for triangulate_fn, sys.modules mocking
  - Transpose validation: `tests/test_axis_alignment.py:80-120` — Existing pattern for assertion
  - Non-canonical axis example: 45° rotation in XY plane: `dir_X = [1/√2, 1/√2, 0]`, `dir_Y = [-1/√2, 1/√2, 0]`, `dir_Z = [0, 0, 1]`
  - Left-handed example: `cross(dir_X, dir_Y) = -dir_Z` (reverses one component)

  **Acceptance Criteria**:
  - [ ] File `tests/test_axis_alignment_transpose.py` created with **two test functions**
  - [ ] Test 1: Uses non-canonical (45° rotated) landmark directions
  - [ ] Test 1: Verifies `np.testing.assert_allclose(R_world @ dir_X, [1,0,0], atol=1e-6)` and same for Y, Z
  - [ ] Test 2: Uses left-handed landmark triad (exercises `det < 0` path)
  - [ ] Test 2: Verifies `det(R_world) ≈ +1.0` and direction mapping correctness
  - [ ] Both tests pass: `pytest tests/test_axis_alignment_transpose.py -v`
  - [ ] Tests follow no-fixture pattern from existing `test_axis_alignment.py`
  - [ ] Sensitivity check: reverting **BOTH** lines 812 and 820 causes tests to fail

  **QA Scenarios**:
  ```
  Scenario: Both tests run and pass with transposed fix
    Tool: Bash (pytest)
    Steps: conda run -n OpenLPT python -m pytest tests/test_axis_alignment_transpose.py::test_axis_alignment_non_aligned_landmarks tests/test_axis_alignment_transpose.py::test_axis_alignment_left_handed_triad -v
    Expected: Both tests PASSED
    Evidence: .sisyphus/evidence/task-2-both-tests-pass.txt

  Scenario: Tests fail without transpose (sensitivity check)
    Tool: Bash (manual revert + pytest)
    Steps: 
      1. Temporarily revert lines 812 and 820 to `R_new = U @ Vt` and `R_new = U_fix @ Vt`
      2. Run: conda run -n OpenLPT python -m pytest tests/test_axis_alignment_transpose.py -v
      3. Restore the transpose fix
    Expected: Tests FAIL without transpose (proves test is sensitive to fix)
    Evidence: .sisyphus/evidence/task-2-test-sensitivity.txt

  Scenario: Existing tests still pass (no regression)
    Tool: Bash (pytest)
    Steps: conda run -n OpenLPT python -m pytest tests/test_axis_alignment.py -v
    Expected: All existing tests PASSED (same as before fix)
    Evidence: .sisyphus/evidence/task-2-no-regression.txt
  ```

  **Commit**: YES | Message: `test(geometry): add regression tests for axis alignment transpose fix` | Files: `tests/test_axis_alignment_transpose.py`

---

- [ ] 3. Verify all axis-alignment tests pass (no regressions)

  **What to do**:
  - Run full test suite: `pytest tests/test_axis_alignment.py tests/test_axis_alignment_transpose.py -v`
  - Confirm all tests pass (original 7+ plus 2 new tests from Task 2)
  - Capture output to evidence file
  - No tests skipped or failed

  **Must NOT do**:
  - Do not modify test code
  - Do not skip any tests
  - Do not use GUI/interactive tests

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Run existing test suite
  - Skills: [] — Reason: No special skills
  - Omitted: — Reason: N/A

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [Task 4] | Blocked By: [Task 2]

  **References**:
  - Existing tests: `tests/test_axis_alignment.py` — Should all still pass with correct transpose
  - New tests: `tests/test_axis_alignment_transpose.py` (from Task 2) — 2 new tests
  - Both files imported from module: `modules/camera_calibration/wand_calibration/refractive_geometry.py`

  **Acceptance Criteria**:
  - [ ] All existing tests in `test_axis_alignment.py` still pass (≥7 tests)
  - [ ] Both new tests in `test_axis_alignment_transpose.py` pass
  - [ ] Total: ≥9 tests passed (7 original + 2 new minimum)
  - [ ] No failures, no skipped tests
  - [ ] Exit code 0 from pytest
  - [ ] Output contains: `passed` count ≥9

  **QA Scenarios**:
  ```
  Scenario: Full test suite passes with both files
    Tool: Bash (pytest)
    Steps: conda run -n OpenLPT python -m pytest tests/test_axis_alignment.py tests/test_axis_alignment_transpose.py -v --tb=short 2>&1 | tee .sisyphus/evidence/task-3-full-test-output.txt
    Expected: All tests PASSED, exit code 0, "passed" count ≥9
    Evidence: .sisyphus/evidence/task-3-full-test-output.txt

  Scenario: Count test results
    Tool: Bash (pytest with count)
    Steps: conda run -n OpenLPT python -m pytest tests/test_axis_alignment.py tests/test_axis_alignment_transpose.py -v 2>&1 | grep -E "passed|failed"
    Expected: Line contains "passed" (no "failed"), count ≥9
    Evidence: .sisyphus/evidence/task-3-test-count.txt
  ```

  **Commit**: NO (compilation check only, no code changes)

---

- [ ] 4. Verify 3D view renders aligned cameras/points

  **What to do**:
  - Use Calibration3DViewer.plot_calibration() directly with axis-aligned landmarks
  - Verify camera frustums point in correct directions and 3D points form an aligned structure
  - Create a simple unit test that calls plot_calibration with known aligned params
  - (Optional: Manual visual check in GUI if time permits)

  **Must NOT do**:
  - Do not use Playwright/GUI automation (unit tests only, or manual review)
  - Do not modify viewer code
  - Do not require user interaction

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Requires integration with viewer + visualization validation
  - Skills: [] — Reason: Standard test setup
  - Omitted: — Reason: N/A

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: none | Blocked By: [Task 3]

  **References**:
  - Viewer code: `modules/camera_calibration/view.py:5419-5447` — `_update_3d_viz()` and `plot_calibration()` call
  - Test fixture pattern: `tests/test_precalibrate_3d_view.py:1-50` — Mock matplotlib, test plot_calibration output
  - Camera frustum rendering: `modules/camera_calibration/calibration_3d_view.py` — Check how R/T are used to render frustum

  **Acceptance Criteria**:
  - [ ] Test creates known aligned camera extrinsics (e.g., camera center at origin, looking down +Z)
  - [ ] Test calls plot_calibration with those params + aligned 3D points
  - [ ] Test verifies: camera frustum renders pointing in expected direction (unit test assertion, or manual visual confirmation)
  - [ ] 3D points render at expected positions (again, unit assertion or visual)

  **QA Scenarios**:
  ```
  Scenario: Unit test validates camera frustum alignment
    Tool: Python (unit test in pytest)
    Steps: 
      1. Create mock viewer with aligned extrinsics
      2. Call plot_calibration(cameras, points_3d)
      3. Assert camera frustum vertices are at expected positions in new frame
    Expected: Assertions pass (frustum aligned to world axes)
    Evidence: .sisyphus/evidence/task-4-frustum-alignment.txt

  Scenario: Manual visual check (optional, if GUI available)
    Tool: GUI / Calibration3DViewer
    Steps: 
      1. Load pre-calibrated project with axis alignment
      2. Click "Precalibrate to Check"
      3. View 3D tab after alignment message
    Expected: Camera frustums and 3D points visually align to axis directions
    Evidence: Screenshot or user confirmation
  ```

  **Commit**: YES | Message: `test(viewer): add integration test for 3D alignment rendering` | Files: `tests/test_3d_view_alignment_rendering.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

**Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**

---

## Commit Strategy

Two atomic commits (note: Task 1 now includes BOTH lines):
1. `fix(geometry): correct R_new transpose in axis alignment basis construction` — Lines 812 AND 820 in `refractive_geometry.py` (single commit, both fixes same root cause)
2. `test(geometry): add regression tests for axis alignment transpose fix` — `tests/test_axis_alignment_transpose.py` (two test functions)

---

## Success Criteria

1. ✅ **Lines 812 AND 820** of `refractive_geometry.py` are changed to use `.T` transpose
   - Line 812: `R_new = (U @ Vt).T`
   - Line 820: `R_new = (U_fix @ Vt).T`
2. ✅ **Two regression tests** created and passing:
   - Non-aligned landmarks (45° rotated) test
   - Left-handed triad test (exercises `det < 0` path)
3. ✅ All existing axis-alignment tests still pass (no regressions)
4. ✅ **Direction mapping assertions** verify: `R_world @ dir_X ≈ [1,0,0]` (and Y, Z) with tolerance 1e-6
5. ✅ **Sensitivity check** proves tests fail when transpose fix is reverted
6. ✅ No bare `U @ Vt` or `U_fix @ Vt` assignments remain (verified via regex)
7. ✅ User confirms: after "Precalibrate to Check", camera frustums and 3D points are now properly aligned in the 3D view

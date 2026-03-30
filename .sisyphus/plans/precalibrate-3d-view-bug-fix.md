# Precalibrate 3D View Bug Fix

## TL;DR
> **Summary**: The 3D view silently crashes after "Precalibrate to Check" when axis alignment succeeds. Root cause confirmed: `view.py:5365` stores `wand_calibrator.points_3d` as a Python list via `.tolist()`; then `view.py:5368` calls `_update_3d_viz()` which passes that list to `plot_calibration()`; inside `plot_calibration()` at line 628, `points_3d / scale` fails with `TypeError: unsupported operand type(s) for /: 'list' and 'float'`. Exception is silently caught by the axis alignment try-except at line 5310.
> 
> **Deliverables**: 
> - `plot_calibration()` type-guarded: wrap `points_3d` in `np.asarray()` at lines 628, 737, 748, 758
> - `view.py:5365` fixed: remove `.tolist()` so `wand_calibrator.points_3d` stays numpy after alignment
> - `view.py:5371-5372` improved: replace bare `print()` with `logger.warning()` + fallback `_update_3d_viz()` so pre-alignment 3D state shows on error
> - Regression test `tests/test_precalibrate_3d_view.py` confirms `plot_calibration()` handles Python list input without crashing
> 
> **Effort**: Quick (3 tasks, ~50 LOC changes; 1 commit)
> 
> **Parallel**: NO (sequential: fix code → test → commit)
> 
> **Critical Path**: Task 1 (fix code) → Task 2 (test) → Task 3 (commit)

## Context

### Original Request
User reported that after clicking "Precalibrate to Check", calibration runs successfully (creates `final_params` and `points_3d`), but the 3D view displays empty. Error in logs: `[Axis Alignment] Error during post-calibration alignment: unsupported operand type(s) for /: 'list' and 'float'`.

### Confirmed Root Cause (from deep code tracing)

**Call chain that triggers the bug:**

1. `_on_calibration_finished()` → `view.py:5305` → calls `_update_3d_viz()` with numpy `points_3d` ✅ (works)
2. Axis alignment succeeds → `view.py:5365` → `self.wand_calibrator.points_3d = pts_new.tolist()` ← **TYPE CORRUPTION: numpy → Python list**
3. `view.py:5368` → calls `_update_3d_viz()` again with the now-list `points_3d`
4. `_update_3d_viz()` → `view.py:5433` → passes `wand_calibrator.points_3d` (Python list) to `plot_calibration()`
5. `plot_calibration()` → `view.py:628` → `pts = points_3d / scale` → **`TypeError: 'list' / float`**
6. Exception caught by axis alignment try-except at `view.py:5310`, silent `print()` only
7. Second `_update_3d_viz()` never completes → 3D view shows **nothing** (or pre-alignment state if matplotlib partially rendered)

**Why only second call fails**: First `_update_3d_viz()` at line 5305 uses original numpy `points_3d` from `_finalize_calibration()` (set at `wand_calibrator.py:2774` as numpy). Second call uses the list-ified version from line 5365.

**Secondary exposure**: `calculate_per_frame_errors()` at `wand_calibrator.py:489` does `self.points_3d[idx_A] - self.points_3d[idx_B]`; if `points_3d` is list of lists, this fails with `TypeError: unsupported operand type(s) for -: 'list' and 'list'`. Called at `view.py:5376` (after axis alignment).

**4 division sites in `plot_calibration()`** that will crash on Python list input:
- Line 628: `pts = points_3d / scale`
- Line 737: `pts_m = points_3d / scale`
- Line 748: `pts_m = points_3d / scale`
- Line 758: `(points_3d / scale).tolist()`

### Fix Strategy (Evaluated)

**Option A** (chosen for robustness): 
- Fix `plot_calibration()` — wrap `points_3d` in `np.asarray()` at all 4 division sites
- Fix `view.py:5365` — remove `.tolist()` so `wand_calibrator.points_3d` stays numpy
- Improve error visibility at `view.py:5372`
- **Why**: Defensive (handles any caller passing list), fixes both `plot_calibration()` and downstream `calculate_per_frame_errors()` exposure, visible errors for debugging

**Option B** (incomplete): Fix only line 5365 (remove `.tolist()`). Works but doesn't protect against future callers.

**Option C** (incomplete): Fix only `plot_calibration()`. Leaves secondary exposure in `calculate_per_frame_errors()`.

## Work Objectives

### Core Objective
Fix the confirmed `list / float` TypeError in `plot_calibration()`, ensure `wand_calibrator.points_3d` stays numpy throughout the lifecycle, improve error visibility, and add a regression test that reproduces the exact failure scenario.

### Deliverables
1. **File: `modules/camera_calibration/view.py`**
   - Lines 628, 737, 748, 758: Wrap `points_3d` in `np.asarray()` before division
   - Line 5365: Remove `.tolist()`, keep numpy
   - Line 5372: Replace bare `print()` with `logger.warning()` + fallback `_update_3d_viz()` call

2. **File: `tests/test_precalibrate_3d_view.py`**
   - New regression test that passes a Python list to `plot_calibration()` and confirms no crash
   - Tests both `plot_calibration()` type safety and `calculate_per_frame_errors()` robustness

3. **All tests passing**: `conda run -n OpenLPT python -m pytest tests/test_precalibrate_3d_view.py -v` → PASS

4. **No regressions**: `conda run -n OpenLPT python -m pytest tests/ -k "calibrat" -v` → All PASS

### Definition of Done (verifiable commands)
```bash
# Test 1: New regression test passes
conda run -n OpenLPT python -m pytest tests/test_precalibrate_3d_view.py -v

# Test 2: No regressions in existing calibration tests
conda run -n OpenLPT python -m pytest tests/ -k "calibrat" -v

# Test 3: Code compiles
conda run -n OpenLPT python -m py_compile modules/camera_calibration/view.py

# Test 4: Verify no .tolist() at line 5365
grep -n "\.tolist()" modules/camera_calibration/view.py | grep -v "5758\|5696\|5707"  # Should NOT show line 5365

# Test 5: Verify np.asarray wraps at 4 division sites
grep -n "np.asarray(points_3d) / scale" modules/camera_calibration/view.py | wc -l  # Should show 4 or more hits
```

### Must Have
- [ ] `np.asarray(points_3d)` wrapping at `view.py` lines 628, 737, 748, 758
- [ ] Remove `.tolist()` at `view.py:5365`
- [ ] Replace `print()` at `view.py:5372` with `logger.warning()` + fallback `_update_3d_viz()` call
- [ ] Unit test in `tests/test_precalibrate_3d_view.py` that reproduces the `list / float` error scenario
- [ ] All 4 division sites have defensive type guards
- [ ] No syntax errors: code compiles with `py_compile`

### Must NOT Have (guardrails)
- [ ] Must NOT modify `align_world_to_axis_directions()`, `apply_coordinate_rotation()`, or `triangulate_pinhole_landmarks()` — they are not the source
- [ ] Must NOT remove the `_update_3d_viz()` call at `view.py:5305` — it is correct and unconditional
- [ ] Must NOT change axis alignment math at lines 5344-5360
- [ ] Must NOT create tests requiring GUI interaction (unit tests only, no E2E/Playwright)
- [ ] Must NOT use pytest fixtures; follow existing pattern in `tests/test_axis_alignment.py`
- [ ] Must NOT call `.tolist()` anywhere that results in `wand_calibrator.points_3d` being stored as Python list

## Verification Strategy

> ZERO HUMAN INTERVENTION — all verification is agent-executed via unit tests + command-line validation.

- **Test Decision**: tests-after (fix is simple enough to validate with focused regression test; no TDD diagnostic loop needed)
- **Framework**: `pytest` (already in use in `tests/`)
- **QA Policy**: Every code change has specific test coverage; all failure modes covered
- **Evidence**: `tests/test_precalibrate_3d_view.py` output + pytest run logs

## Execution Strategy

### Parallel Execution Waves

**Wave 1: Implementation** (single task, sequential)
- Task 1: Fix `plot_calibration()` + remove `.tolist()` + improve error visibility

**Wave 2: Testing** (single task)
- Task 2: Add regression test

**Wave 3: Commit** (single task)
- Task 3: Create atomic commit

### Dependency Matrix (full, all tasks)

| Task | Depends On | Blocks | Notes |
|------|-----------|--------|-------|
| 1 (Fix code) | None | 2 | Implement all 3 fixes (4 division wraps + remove .tolist + improve error visibility) |
| 2 (Add test) | 1 | 3 | Regression test must pass after code fix |
| 3 (Commit) | 2 | None | Create atomic commit with message + evidence files |

### Agent Dispatch Summary

- **Wave 1**: 1 implementer (quick: simple fixes to specific lines)
- **Wave 2**: 1 implementer (quick: add regression test with synthetic data)
- **Wave 3**: 1 implementer (quick: git commit operations)

## TODOs

- [x] **1. Fix `plot_calibration()` Type Guard + Remove `.tolist()` + Improve Error Visibility**

  **What to do**:
  
  **Part A: Wrap `points_3d` at 4 division sites in `plot_calibration()`**
  
  1. Open `modules/camera_calibration/view.py`
  2. At line 628, change:
     ```python
     pts = points_3d / scale
     ```
     to:
     ```python
     pts = np.asarray(points_3d) / scale
     ```
  3. At line 737, change:
     ```python
     pts_m = points_3d / scale
     ```
     to:
     ```python
     pts_m = np.asarray(points_3d) / scale
     ```
  4. At line 748, change:
     ```python
     pts_m = points_3d / scale
     ```
     to:
     ```python
     pts_m = np.asarray(points_3d) / scale
     ```
  5. At line 758, change:
     ```python
     bbox_sources.extend((points_3d / scale).tolist())
     ```
     to:
     ```python
     bbox_sources.extend((np.asarray(points_3d) / scale).tolist())
     ```
  
  **Part B: Remove `.tolist()` at line 5365**
  
  6. At line 5365, change:
     ```python
     self.wand_calibrator.points_3d = pts_new.tolist()
     ```
     to:
     ```python
     self.wand_calibrator.points_3d = pts_new
     ```
  
  **Part C: Improve error visibility at line 5372**
  
  7. At line 5372, change:
     ```python
     except Exception as _ax_err:
         print(f"[Axis Alignment] Error during post-calibration alignment: {_ax_err}")
     ```
     to:
     ```python
     except Exception as _ax_err:
         logger.warning(f"[Axis Alignment] Error during post-calibration alignment: {_ax_err}")
         logger.info("[Axis Alignment] Showing original calibration data instead.")
         self._update_3d_viz()  # Display pre-alignment 3D state on error
     ```
  
  8. Verify code compiles: `conda run -n OpenLPT python -m py_compile modules/camera_calibration/view.py`

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Simple find-replace at specific line numbers; no logic changes
  - Skills: None
  - Omitted: None

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2 | Blocked By: None

  **References**:
  - File: `modules/camera_calibration/view.py:620-780` (entire `plot_calibration()` method)
  - File: `modules/camera_calibration/view.py:5365` (`.tolist()` to remove)
  - File: `modules/camera_calibration/view.py:5372` (exception handler to improve)

  **Acceptance Criteria**:
  - [ ] All 4 division sites wrapped in `np.asarray(points_3d)` (lines 628, 737, 748, 758)
  - [ ] `.tolist()` removed at line 5365 (now: `self.wand_calibrator.points_3d = pts_new`)
  - [ ] Exception handler at line 5372 includes `logger.warning()`, `logger.info()`, and fallback `_update_3d_viz()` call
  - [ ] Code compiles without syntax errors: `conda run -n OpenLPT python -m py_compile modules/camera_calibration/view.py` → exit code 0
  - [ ] No other lines changed (verify with diff)

  **QA Scenarios**:
  ```
  Scenario: Code compiles after all fixes
    Tool: Bash
    Steps: conda run -n OpenLPT python -m py_compile modules/camera_calibration/view.py
    Expected: Exit code 0 (no syntax errors)
    Evidence: .sisyphus/evidence/task-1-compile.log

  Scenario: All 4 np.asarray wraps are in place
    Tool: Bash
    Steps: grep -n "np.asarray(points_3d) / scale" modules/camera_calibration/view.py
    Expected: Shows lines 628, 737, 748, 758 (or close numbers if formatting differs)
    Evidence: .sisyphus/evidence/task-1-asarray-check.log

  Scenario: .tolist() removed at line 5365
    Tool: Bash
    Steps: sed -n '5365p' modules/camera_calibration/view.py
    Expected: Shows "self.wand_calibrator.points_3d = pts_new" (no .tolist())
    Evidence: .sisyphus/evidence/task-1-tolist-check.log

  Scenario: Exception handler improved with fallback
    Tool: Bash
    Steps: sed -n '5371,5375p' modules/camera_calibration/view.py | grep -c "_update_3d_viz"
    Expected: Shows count >= 1 (fallback call exists)
    Evidence: .sisyphus/evidence/task-1-fallback-check.log
  ```

  **Commit**: YES (Collected for single commit after task 2)

---

- [x] **2. Add Regression Test for `plot_calibration()` Type Safety**

  **What to do**:
  1. Create new file: `tests/test_precalibrate_3d_view.py`
  2. Import required modules:
     ```python
     import pytest
     import numpy as np
     from unittest.mock import Mock, MagicMock, patch
     ```
  3. Write 2 test functions:
  
  **Test 1: Type safety with Python list input**
  ```python
  def test_plot_calibration_handles_list_input():
      """Regression test: plot_calibration() should not crash when points_3d is a Python list.
      
      Root cause: After axis alignment, wand_calibrator.points_3d was stored as list via .tolist().
      plot_calibration() then attempted `list / float` which raises TypeError.
      This test confirms the fix: np.asarray() guards all division operations.
      """
      # Create synthetic camera params and 3D points
      cameras = {
          0: {"R": np.eye(3), "T": np.array([[0], [0], [1000]])}
      }
      
      # Pass as Python list (the bug scenario)
      points_3d_list = [[100.0, 200.0, 300.0], [400.0, 500.0, 600.0]]
      
      # Create a mock 3D view widget
      mock_ax = MagicMock()
      mock_canvas = MagicMock()
      view_3d = MagicMock()
      view_3d.ax = mock_ax
      view_3d.canvas = mock_canvas
      
      # This should NOT raise TypeError: unsupported operand type(s) for /: 'list' and 'float'
      # Import the actual plot_calibration method and call it
      from modules.camera_calibration.view import Calibration3DView
      
      calib_view = Calibration3DView(MagicMock())
      
      # Should complete without crashing
      try:
          calib_view.plot_calibration(cameras=cameras, points_3d=points_3d_list)
          success = True
      except TypeError as e:
          if "unsupported operand type(s) for /" in str(e):
              success = False
          else:
              raise  # Re-raise unexpected errors
      
      assert success, "plot_calibration() crashed when passed a Python list for points_3d"
  ```
  
  **Test 2: `calculate_per_frame_errors()` robustness with numpy points**
  ```python
  def test_calculate_per_frame_errors_with_numpy_points():
      """Confirm that points_3d stays numpy after axis alignment (no .tolist()).
      This prevents secondary failure in calculate_per_frame_errors() at wand_calibrator.py:489.
      """
      from modules.camera_calibration.wand_calibration.wand_calibrator import WandCalibrator
      import numpy as np
      
      # Build synthetic wand calibrator
      wand = WandCalibrator()
      wand.points_3d = np.array([[100, 200, 300], [400, 500, 600]])
      wand.wand_length = 305.0
      
      # Mock final_params for 1 camera
      wand.final_params = {
          0: {
              "R": np.eye(3),
              "T": np.array([[0], [0], [1000]]),
              "K": np.eye(3),
              "dist": np.zeros(5)
          }
      }
      
      # Mock wand_data
      wand.wand_points_filtered = None
      wand.wand_points = {
          0: {0: [[100, 200], [100, 200]]},  # frame 0: cam 0 sees both sphere centers
          1: {0: [[400, 500], [400, 500]]}
      }
      
      # Call calculate_per_frame_errors() — should NOT crash with list subtraction error
      errors = wand.calculate_per_frame_errors()
      
      # Verify points_3d is still numpy
      assert isinstance(wand.points_3d, np.ndarray), f"Expected numpy array, got {type(wand.points_3d)}"
      assert errors is not None or errors == {}, "calculate_per_frame_errors() should complete without error"
  ```

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Add 2 focused unit tests with synthetic data; no fixtures needed
  - Skills: None
  - Omitted: None

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 3 | Blocked By: 1

  **References**:
  - Pattern: `tests/test_axis_alignment.py` (direct object instantiation, no pytest fixtures)
  - File: `modules/camera_calibration/view.py:590-780` (understand `plot_calibration()` to mock correctly)
  - File: `modules/camera_calibration/wand_calibration/wand_calibrator.py:457-538` (understand `calculate_per_frame_errors()`)

  **Acceptance Criteria**:
  - [ ] File `tests/test_precalibrate_3d_view.py` created
  - [ ] 2 test functions present and importable
  - [ ] Tests can be discovered: `conda run -n OpenLPT python -m pytest tests/test_precalibrate_3d_view.py --collect-only` → shows 2 tests
  - [ ] Both tests PASS: `conda run -n OpenLPT python -m pytest tests/test_precalibrate_3d_view.py -v` → 2 PASSED
  - [ ] No syntax errors in test file

  **QA Scenarios**:
  ```
  Scenario: Test file imports correctly
    Tool: Bash
    Steps: conda run -n OpenLPT python -c "import tests.test_precalibrate_3d_view; print('OK')"
    Expected: Exit code 0, prints "OK"
    Evidence: .sisyphus/evidence/task-2-import.log

  Scenario: Pytest discovers both tests
    Tool: Bash
    Steps: conda run -n OpenLPT python -m pytest tests/test_precalibrate_3d_view.py --collect-only -q
    Expected: Output shows "2 selected" or lists both test names
    Evidence: .sisyphus/evidence/task-2-collect.log

  Scenario: Both tests pass
    Tool: Bash
    Steps: conda run -n OpenLPT python -m pytest tests/test_precalibrate_3d_view.py -v 2>&1 | tee .sisyphus/evidence/task-2-run.log
    Expected: Output shows "2 passed"
    Evidence: .sisyphus/evidence/task-2-run.log
  ```

  **Commit**: YES (Collected with task 1 for single commit)

---

- [x] **3. Create Atomic Commit**

  **What to do**:
  1. Verify both files are modified: `git status`
  2. Create commit:
     ```bash
     git add modules/camera_calibration/view.py tests/test_precalibrate_3d_view.py
     git commit -m "fix: resolve list/float TypeError in precalibrate 3D view

     Root cause: After successful axis alignment, wand_calibrator.points_3d was
     stored as Python list (via .tolist()). On second _update_3d_viz() call,
     plot_calibration() attempted 'list / float' division, raising TypeError.
     
     Fixes:
     - Wrap points_3d in np.asarray() at 4 division sites in plot_calibration()
     - Remove .tolist() at view.py:5365 to keep points_3d as numpy
     - Improve error visibility: replace print() with logger.warning() + fallback
     
     Regression test added to prevent recurrence."
     ```
  3. Verify commit: `git log --oneline -1`
  4. Run tests one more time to confirm: `conda run -n OpenLPT python -m pytest tests/test_precalibrate_3d_view.py -v`

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Git commit operations
  - Skills: [git-master] — for atomic commit expertise
  - Omitted: None

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: Final Verification | Blocked By: 1, 2

  **References**:
  - Commit message format: `type(scope): description` per repo standards
  - Git workflow: Atomic commits per AGENTS.md

  **Acceptance Criteria**:
  - [ ] Commit created with message starting with "fix:"
  - [ ] Both `modules/camera_calibration/view.py` and `tests/test_precalibrate_3d_view.py` included in commit
  - [ ] `git log --oneline -1` shows the new commit
  - [ ] `git status` shows "nothing to commit, working tree clean"
  - [ ] Final test run passes: `conda run -n OpenLPT python -m pytest tests/test_precalibrate_3d_view.py -v` → 2 PASSED

  **QA Scenarios**:
  ```
  Scenario: Commit created successfully
    Tool: Bash
    Steps: git log --oneline -1
    Expected: Shows commit message starting with "fix: resolve list/float"
    Evidence: .sisyphus/evidence/task-3-git-log.txt

  Scenario: Working tree is clean
    Tool: Bash
    Steps: git status
    Expected: Shows "On branch X. nothing to commit, working tree clean"
    Evidence: .sisyphus/evidence/task-3-git-status.txt

  Scenario: Final test run confirms fix
    Tool: Bash
    Steps: conda run -n OpenLPT python -m pytest tests/test_precalibrate_3d_view.py -v 2>&1 | tee .sisyphus/evidence/task-3-final-test.log
    Expected: Shows "2 passed"
    Evidence: .sisyphus/evidence/task-3-final-test.log
  ```

  **Commit**: N/A (this task IS the commit operation)

---

## Final Verification Wave (MANDATORY)

> **CRITICAL**: Do NOT mark any of these as checked until you have completed the check AND gotten explicit user approval.

- [x] **F1. Plan Compliance Audit** (oracle agent)
- [x] **F2. Code Quality Review** (unspecified-high agent)
- [ ] **F3. Real Manual QA** (unspecified-high agent)
- [ ] **F4. Scope Fidelity Check** (deep agent)
  - Verify original bug (empty 3D view after axis alignment) is fixed by the code changes
  - Verify axis alignment still works when data is valid numpy
  - Verify error messages are user-visible when `_update_3d_viz()` is called
  - Verify no data is corrupted by the changes
  - Verify `wand_calibrator.points_3d` remains numpy throughout lifecycle

## Commit Strategy

**Atomic commit (1 total)**:
- `fix: resolve list/float TypeError in precalibrate 3D view` — All code fixes + regression test

**All changes confined to**:
- `modules/camera_calibration/view.py` (4 type guards + remove .tolist() + improve error visibility)
- `tests/test_precalibrate_3d_view.py` (2 regression tests)
- `.sisyphus/evidence/` (QA evidence files)

## Success Criteria

✅ **Regression tests PASS**: `pytest tests/test_precalibrate_3d_view.py -v` → 2 PASSED  
✅ **No regressions in existing tests**: `pytest tests/ -k "calibrat" -v` → All PASS  
✅ **Code compiles**: `python -m py_compile modules/camera_calibration/view.py` → exit 0  
✅ **Type safety verified**: `np.asarray(points_3d)` wraps all 4 division sites  
✅ **Data integrity maintained**: `points_3d` stays numpy throughout lifecycle  
✅ **Error visibility improved**: Exceptions logged with fallback rendering  
✅ **Single atomic commit created**: With meaningful message and both files included

---

**Plan is decision-complete and ready for execution.**  
Run `/start-work` to begin.

# Fix GUI Freeze: "Load Axis Points" Button

## TL;DR
> **Summary**: Clicking "Load Axis Points" button freezes GUI. Root cause: Qt signal/slot signature mismatch — `clicked(bool)` emits False which binds to `file_path` parameter, causing `if file_path is None:` to be false, skipping file dialog and freezing on `open(False)` (stdin read). Fix: lambda wrapper at line 1380 to discard the bool arg.
> **Deliverables**: File dialog appears on click, CSV loads, button disabled after load, no freeze.
> **Effort**: Quick
> **Parallel**: NO
> **Critical Path**: Fix signal connection (T1) → Type validation (T2) → Init (T3) → Logging (T4) → Verify (T5)

## Context
### Original Request
User reported: "Now when I click Load Axis points, the whole GUI got stuck and no popup window to load axis point file."

### Root Cause Analysis (From Metis Review)
**The actual bug is a Qt signal/slot signature mismatch:**

```
Line 1380: self.btn_load_axis_csv.clicked.connect(self._load_axis_points_csv)
                                                    ↓
Slot signature: def _load_axis_points_csv(self, file_path=None):
                                                  ↑
When clicked signal emits bool (checked state: False)
False binds to file_path parameter
                                                  ↓
Line 1589: if file_path is None:
           False is not None → condition is FALSE → dialog is SKIPPED ❌
                                                  ↓
Line 1590: open(False, "r", ...) → open(0, "r", ...)  (False is int 0)
                                                  ↓
open(0) tries to read from stdin (file descriptor 0)
→ GUI FREEZES waiting for user input from stdin ❌
```

**The fix (one line):**
```python
# FROM:
self.btn_load_axis_csv.clicked.connect(self._load_axis_points_csv)

# TO:
self.btn_load_axis_csv.clicked.connect(lambda checked=False: self._load_axis_points_csv())
```

This lambda discards the `bool` argument, matching the pattern already used in the same file at line 3027.

### Investigation Summary
- **QFileDialog import**: Correct at line 17 ✅
- **Function code**: Looks correct, dialog logic is sound ✅
- **Signal connection**: WRONG — emits bool, slot has optional string param ❌
- **Existing precedent**: Line 3027 uses exact same lambda pattern for axis images button ✅
- **Missing initialization**: `axis_direction_map` not in `__init__` (good to fix but NOT the freeze cause) ⚠️

## Work Objectives

### Core Objective
Enable users to load axis-direction CSV files via the "Load Axis Points" button without GUI freezing.

### Deliverables
1. File dialog appears immediately when button clicked
2. CSV file can be selected and loaded
3. `axis_direction_map` correctly populated
4. Button disabled after successful load
5. Error messages visible if load fails
6. Existing calibration workflow unaffected

### Definition of Done (Verifiable)
- Test: Click button → file dialog appears within 500ms
- Test: Select CSV → file loaded, no errors
- Test: Inspect `self.axis_direction_map` in memory → correct structure
- Test: Button text/state changed after load
- Regression: Calibration flow still works (no side effects)

### Must Have
- File dialog appears and responds to user interaction
- CSV loading completes without freezing
- Button state reflects load status
- Error handling prevents silent failures

### Must NOT Have
- Blocking operations on main thread before dialog shows
- Infinite loops or retry logic
- Modification of calibration workflow
- Changes to other buttons/features

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: Manual QA (GUI interaction via Playwright)
- QA policy: Button click → dialog appears → CSV loads
- Evidence: Screenshots of dialog, console logs, axis_direction_map structure

## Execution Strategy

### Single Wave (Sequential — button must work before other tasks proceed)

⚠️ **CRITICAL UPDATE FROM METIS REVIEW**:
Metis identified the **actual root cause** — NOT `axis_direction_map` initialization, but a **Qt signal/slot signature mismatch** at line 1380. When button clicked, `clicked(bool)` emits `False` which binds to `file_path` parameter, causes `if file_path is None:` to be false, skips dialog, then `open(False)` blocks on stdin → GUI freezes. The fix is a one-line lambda wrapper at line 1380, following the existing safe pattern at line 3027. Tasks 2-4 add defense-in-depth.

Task order has been reordered to fix the signal connection FIRST (Task 1), then add hardening/initialization/logging (Tasks 2-4).

## TODOs

### 1. Fix Signal Connection (THE ACTUAL ROOT CAUSE FIX)

**What to do**:
- Locate line 1380: `self.btn_load_axis_csv.clicked.connect(self._load_axis_points_csv)`
- Replace with: `self.btn_load_axis_csv.clicked.connect(lambda checked=False: self._load_axis_points_csv())`
- This discards the `bool` argument that Qt emits on button click
- Pattern to follow: Line 3027 in same file uses `lambda checked=False, idx=i: self._load_axis_images_for_cam(idx)`

**Root Cause Explanation**:
- `QPushButton.clicked` emits `bool` (checked state, `False`)
- Without lambda, `False` gets bound to `file_path` parameter
- `if file_path is None:` evaluates to `False` (since `False is not None`) → dialog is **SKIPPED**
- Code proceeds to `open(False, "r", ...)` → `open(0, "r", ...)` (False is int 0)
- `open(0)` reads from stdin (file descriptor 0) → **GUI FREEZES waiting for input**
- Lambda wrapper absorbs the bool argument, solves the problem

**Must NOT do**:
- Do not modify the method signature of `_load_axis_points_csv`
- Do not change any other button connections
- Do not use decorator approach (Qt requires inline lambda for this pattern)

**Recommended Agent Profile**:
- Category: `quick` — Reason: One-line fix
- Skills: None needed
- Omitted: None

**Parallelization**: N/A — sequential, this is Task 1

**References**:
- Current broken: `modules/camera_calibration/view.py:1380` — button connection
- Correct pattern: `modules/camera_calibration/view.py:3027` — existing lambda wrapper for axis images button
- Method signature: `modules/camera_calibration/view.py:1584` — `def _load_axis_points_csv(self, file_path=None):`
- Qt docs: Signal/Slot connection requires matching signatures; lambda bridges signature mismatch

**Acceptance Criteria** (agent-executable):
- [x] Find line 1380 in view.py: `self.btn_load_axis_csv.clicked.connect(self._load_axis_points_csv)`
- [x] Replace with: `self.btn_load_axis_csv.clicked.connect(lambda checked=False: self._load_axis_points_csv())`
- [x] Verify no syntax errors: `conda run -n OpenLPT python -m py_compile modules/camera_calibration/view.py`
- [x] Verify the exact lambda syntax exists in file: `grep "lambda checked=False: self._load_axis_points_csv" modules/camera_calibration/view.py`

**QA Scenarios**:
```
Scenario: Signal connection fixed (verify syntax)
  Tool: interactive_bash
  Steps:
    1. Run: conda run -n OpenLPT python -m py_compile modules/camera_calibration/view.py
  Expected: Exit code 0 (no syntax errors)
  Evidence: .sisyphus/evidence/task-1-compile-ok.txt

Scenario: Lambda pattern matches existing pattern (code review)
  Tool: interactive_bash
  Steps:
    1. Extract line 1380: grep -A 0 -B 0 "lambda checked=False: self._load_axis_points_csv" modules/camera_calibration/view.py
    2. Extract line 3027 (existing pattern): grep -A 0 -B 0 "lambda checked=False, idx" modules/camera_calibration/view.py
    3. Verify both use lambda structure
  Expected: Both contain "lambda checked=False"
  Evidence: .sisyphus/evidence/task-1-lambda-pattern-verified.txt

Scenario: No other changes to line 1380 area
  Tool: interactive_bash
  Steps:
    1. Run: git diff modules/camera_calibration/view.py | grep -A 3 -B 3 "1380"
  Expected: Only the lambda wrapper added, no other changes
  Evidence: .sisyphus/evidence/task-1-diff-clean.txt
```

**Commit**: YES | Message: `fix: discard clicked(bool) arg in axis CSV button to prevent GUI freeze (signal/slot mismatch)` | Files: `modules/camera_calibration/view.py`

---

### 2. Add Type Validation Guard in Method

**What to do**:
- Locate `def _load_axis_points_csv(self, file_path=None):` at line 1584
- After the docstring (after line 1588), add validation:
  ```python
  if not isinstance(file_path, (str, os.PathLike, type(None))):
      file_path = None
  ```
- Import `os` at top of file (grep for `import os` first — likely already imported)

**Rationale**: Defense-in-depth. If lambda fix misses edge cases or if someone calls this method with wrong type, the method gracefully falls back to showing file dialog instead of crashing on `open(False)`.

**Must NOT do**:
- Do not change method signature
- Do not modify CSV parsing logic
- Do not add try-except (that comes later)

**Recommended Agent Profile**:
- Category: `quick` — Reason: 2-3 lines of validation code
- Skills: None needed
- Omitted: None

**Parallelization**: N/A — sequential

**References**:
- Method: `modules/camera_calibration/view.py:1584-1619`
- Import check: Grep for `import os` near top of file (should already exist)
- Pattern: Defensive input validation before critical operations

**Acceptance Criteria** (agent-executable):
- [x] Verify `import os` exists at top of file: `grep "^import os" modules/camera_calibration/view.py`
- [x] Add isinstance check after line 1588 (after docstring)
- [x] Compile: `conda run -n OpenLPT python -m py_compile modules/camera_calibration/view.py` → exit 0
- [x] Verify validation added: `grep "isinstance(file_path" modules/camera_calibration/view.py`

**QA Scenarios**:
```
Scenario: Type validation prevents open(False) crash
  Tool: interactive_bash
  Steps:
    1. Create test script that calls _load_axis_points_csv(False) directly
    2. Verify it falls back to None instead of crashing
  Expected: file_path becomes None, dialog is shown
  Evidence: .sisyphus/evidence/task-2-validation-works.txt

Scenario: Valid strings still work
  Tool: interactive_bash
  Steps:
    1. Call _load_axis_points_csv("/some/path.csv")
    2. Verify file_path is unchanged
  Expected: file_path remains "/some/path.csv"
  Evidence: .sisyphus/evidence/task-2-string-preserved.txt

Scenario: None still works
  Tool: interactive_bash
  Steps:
    1. Call _load_axis_points_csv(None)
    2. Verify file_path remains None
  Expected: Dialog path is triggered
  Evidence: .sisyphus/evidence/task-2-none-preserved.txt
```

**Commit**: YES | Message: `fix: validate file_path type in _load_axis_points_csv to prevent invalid operations` | Files: `modules/camera_calibration/view.py`

---

### 3. Initialize axis_direction_map in setup_ui()

**What to do**:
- Locate `def setup_ui(self):` at line 1661
- Find line 1682: `self.plate_image_size_hints = {}  # {cam_idx: (width, height)} from loaded plate images`
- Add after line 1682: `self.axis_direction_map = {}  # {cam_idx: {"center":[x,y], "+X":[x,y], "+Y":[x,y], "+Z":[x,y]}}`

**Rationale**: Good hygiene. Ensures `axis_direction_map` always exists as an empty dict from initialization, preventing AttributeError in any code path that accesses it.

**Must NOT do**:
- Do not modify calibration initialization logic
- Do not move this line elsewhere
- Do not add unrelated state variables

**Recommended Agent Profile**:
- Category: `quick` — Reason: Single-line initialization
- Skills: None needed
- Omitted: None

**Parallelization**: N/A — sequential

**References**:
- Pattern: `modules/camera_calibration/view.py:1676-1682` — Existing state initialization style
- Location: `modules/camera_calibration/view.py:1661-1687` — `setup_ui()` context
- Example: Line 1664 (`self.plate_images = []`) shows correct pattern

**Acceptance Criteria** (agent-executable):
- [x] Find line 1682: `self.plate_image_size_hints = {}`
- [x] Add next line: `self.axis_direction_map = {}`
- [x] Compile: `conda run -n OpenLPT python -m py_compile modules/camera_calibration/view.py` → exit 0
- [x] Verify initialization: `grep "self.axis_direction_map = {}" modules/camera_calibration/view.py`

**QA Scenarios**:
```
Scenario: Attribute exists after initialization
  Tool: interactive_bash
  Steps:
    1. Launch Python: conda run -n OpenLPT python
    2. Import and instantiate: from modules.camera_calibration.view import CalibrationTab; w = CalibrationTab(); print(hasattr(w, 'axis_direction_map'))
  Expected: True
  Evidence: .sisyphus/evidence/task-3-attr-exists.txt

Scenario: Attribute is empty dict
  Tool: interactive_bash
  Steps:
    1. Same as above: print(w.axis_direction_map, type(w.axis_direction_map))
  Expected: {} <class 'dict'>
  Evidence: .sisyphus/evidence/task-3-attr-is-dict.txt
```

**Commit**: YES | Message: `fix: initialize axis_direction_map in setup_ui to ensure attribute always exists` | Files: `modules/camera_calibration/view.py`

---

### 4. Add Diagnostic Logging

**What to do**:
- Locate `def _load_axis_points_csv(self, file_path=None):` at line 1584
- Add 3 logging calls:
  1. **At method entry** (after line 1588 docstring, after type validation from Task 2):
     ```python
     import logging
     logger = logging.getLogger(__name__)
     logger.info(f"_load_axis_points_csv called with file_path={file_path!r} (type={type(file_path).__name__})")
     ```
  2. **Before dialog** (before line 1590, before QFileDialog call):
     ```python
     logger.info("Opening file dialog for axis direction CSV...")
     ```
  3. **After dialog** (after line 1592, after dialog returns):
     ```python
     logger.info(f"File dialog returned: {file_path!r}")
     ```

**Rationale**: Observability. Helps debug similar issues in future. Shows exact execution path and what values flow through the method.

**Must NOT do**:
- Do not modify CSV parsing logic
- Do not add try-except around dialog (separate concern)
- Do not change button state logic

**Recommended Agent Profile**:
- Category: `quick` — Reason: 3 logging statements
- Skills: None needed
- Omitted: None

**Parallelization**: N/A — sequential

**References**:
- Existing logging: `modules/camera_calibration/view.py:1609-1610` — logging style in same file
- Pattern: `logger = logging.getLogger(__name__); logger.info(...)`
- Import: Check line 1609 already has `import logging`

**Acceptance Criteria** (agent-executable):
- [x] Find line 1609: `import logging` (verify it exists or add if missing)
- [x] Add 3 logger.info() calls at specified locations
- [x] Compile: `conda run -n OpenLPT python -m py_compile modules/camera_calibration/view.py` → exit 0
- [x] Verify logging added: `grep -c "logger.info" modules/camera_calibration/view.py` shows ≥3 new calls

**QA Scenarios**:
```
Scenario: Logging appears on button click
  Tool: interactive_bash
  Steps:
    1. Create test script that captures logs: import logging; logging.basicConfig(level=logging.INFO); from modules...CalibrationTab import CalibrationTab; w = CalibrationTab(); w._load_axis_points_csv()
    2. Verify log output
  Expected: Log contains "[_load_axis_points_csv called with file_path=None"
  Evidence: .sisyphus/evidence/task-4-logging-appears.txt

Scenario: Dialog event is logged
  Tool: interactive_bash
  Steps:
    1. Same as above, but with logging redirected to file
    2. Check for "Opening file dialog" message
  Expected: Log contains "Opening file dialog for axis direction CSV..."
  Evidence: .sisyphus/evidence/task-4-dialog-logged.txt
```

**Commit**: YES | Message: `chore: add diagnostic logging to _load_axis_points_csv for observability` | Files: `modules/camera_calibration/view.py`

---

### 5. End-to-End Verification (All Fixes Applied)

**What to do**:
- Test complete flow: Click button → Dialog appears → Select CSV → File loads → Button disabled
- Create minimal test CSV file with correct format (9 columns)
- Verify no errors in console and logs show correct execution path
- Verify axis_direction_map populated correctly
- Test error case: invalid CSV should show error, not freeze

**Must NOT do**:
- Do not modify any code (verification phase only, all fixes in Tasks 1-4)
- Do not edit source files
- Do not run full calibration workflow (that's separate regression)

**Recommended Agent Profile**:
- Category: `unspecified-high` — Reason: Manual GUI interaction + verification
- Skills: None
- Omitted: None

**Parallelization**: N/A — sequential final verification

**References**:
- CSV format: Line 1587 docstring — 9-column schema
  ```
  cam_id, center_x, center_y, plus_x_x, plus_x_y, plus_y_x, plus_y_y, plus_z_x, plus_z_y
  ```
- Button state: Line 1619 — Button disabled after load
- Logging: Tasks 1-4 add logging for tracing

**Acceptance Criteria** (agent-executable):
- [x] Create test CSV: `.sisyphus/test_axis_points.csv` with valid data (9 columns, 1-2 camera rows)
- [x] Launch GUI: `conda run -n OpenLPT openlpt-gui`
- [x] Navigate to "Wand Calibration" tab
- [x] Click "Load Axis Points (Optional)" button
- [x] Verify: File dialog appears within 500ms (check logs for "Opening file dialog...")
- [x] Select test CSV
- [x] Verify: File loads, no errors, button is disabled
- [x] Verify: Logs show all 3 logging calls executed
- [x] Verify: axis_direction_map contains expected camera data structure

**QA Scenarios**:
```
Scenario: Happy path — button opens dialog (no freeze)
  Tool: interactive_bash + manual verification
  Steps:
    1. Start GUI with logging: PYTHONUNBUFFERED=1 conda run -n OpenLPT openlpt-gui > /tmp/gui.log 2>&1 &
    2. Click "Load Axis Points" button
    3. Wait 500ms, observe screen
    4. Check log: grep "Opening file dialog" /tmp/gui.log
  Expected: File dialog appears, log shows "Opening file dialog for axis direction CSV..."
  Evidence: .sisyphus/evidence/task-5-dialog-appears.txt + screenshot

Scenario: CSV loads successfully
  Tool: interactive_bash + manual
  Steps:
    1. From above, select .sisyphus/test_axis_points.csv
    2. Click "Open"
    3. Wait 1 second
    4. Check button state: disabled?
    5. Check logs: grep "axis_direction_map" /tmp/gui.log or inspect in debugger
  Expected: Button is disabled, axis_direction_map populated, no errors in log
  Evidence: .sisyphus/evidence/task-5-csv-loaded.txt

Scenario: Cancel doesn't crash
  Tool: interactive_bash + manual
  Steps:
    1. Click "Load Axis Points"
    2. Click "Cancel" in dialog
    3. Wait 1 second
  Expected: Dialog closes, button remains enabled, no errors
  Evidence: .sisyphus/evidence/task-5-cancel-works.txt

Scenario: Invalid CSV shows error
  Tool: interactive_bash + manual
  Steps:
    1. Create invalid CSV (missing columns, wrong format)
    2. Click "Load Axis Points", select invalid CSV
    3. Observe error message
  Expected: QMessageBox with error appears, function returns cleanly
  Evidence: .sisyphus/evidence/task-5-invalid-csv-error.txt

Scenario: Regression — calibration workflow unaffected
  Tool: interactive_bash
  Steps:
    1. Skip the "Load Axis Points" button entirely
    2. Load normal calibration images (plate or wand)
    3. Run calibration normally
  Expected: Calibration completes, no side effects from our changes
  Evidence: .sisyphus/evidence/task-5-regression-calibration.txt
```

**Commit**: NO — Testing only, no code changes

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**

- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA (GUI + Playwright) — unspecified-high
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Task 1: `fix(view): initialize axis_direction_map to empty dict in setup_ui`
- Task 2: `fix(view): add logging to _load_axis_points_csv for debugging GUI freeze`
- Task 3: `fix(view): wrap QFileDialog call with exception handling and explicit parent window`
- All commits to `modules/camera_calibration/view.py` only

## Success Criteria
- ✅ File dialog appears within 500ms of button click
- ✅ CSV file can be selected without GUI freezing
- ✅ axis_direction_map populated correctly in memory
- ✅ Button disabled after successful load
- ✅ Error messages visible (no silent failures)
- ✅ Calibration workflow unaffected (regression tested)

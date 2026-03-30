# Synthetic Validation Harness + Manuscript Outputs

## TL;DR
> **Summary**: Fix the synthetic validation harness so it exercises the refractive calibration path correctly, rerun the full robustness and noise campaigns from clean state, then generate manuscript-ready tables, figures, and a reproducibility manifest from the saved results.
> **Deliverables**:
> - harness fixes in `J:\Refraction_test\test_script\run_calibration_worker.py`
> - launcher fixes in `J:\Refraction_test\test_script\run_robustness.py`, `run_noise_sweep.py`, `run_all_tests.py`
> - fresh robustness and noise result sets under `J:\Refraction_test\test_results`
> - aggregate CSVs, manuscript tables, manuscript figures, run manifest, paper checklist
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: archive stale results → harness fixes → pre-flight checks → bulk reruns → manuscript outputs

## Context

### Original Request
Rewrite the deleted plan for synthetic testing and include the work needed to collect and present results in the manuscript.

### Interview Summary
- The plan file is gone and must be recreated.
- The calibrator under test is `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py`.
- Core algorithm files under `modules/camera_calibration/wand_calibration/` must never be modified.
- Test scripts must remain in `J:\Refraction_test\test_script` and results in `J:\Refraction_test\test_results`.
- Results must be manuscript-ready, not just raw per-case JSONs.
- Every test must run without loading any previous cache, including bootstrap cache.
- The worker must recreate the explanatory notebook that shows how to run the scripts, analyze results, and generate plots.

### Metis Review (gaps addressed)
- Added explicit stale-result archive step before reruns.
- Expanded the fix scope from 3 items to 5 items:
  1. `MockBase.run_precalibration_check`
  2. runtime cache deletion
  3. `sigma=0` noise cache isolation
  4. `as_completed` in all three launchers
  5. manuscript-output generator
- Added guardrail to keep `_extract_metrics` schema unchanged unless a new output layer derives from existing CSVs.
- Added explicit manifest/checklist generation and verification rules.

## Work Objectives

### Core Objective
Produce a clean, reproducible synthetic validation package that runs the refractive wand calibration harness from scratch, saves paper-usable metrics, and emits manuscript-ready outputs without changing the calibration algorithm itself.

### Deliverables
- fixed harness execution path
- fixed launchers for robustness, noise, and combined pipeline
- archived invalid prior results and fresh rerun outputs
- existing aggregate CSVs regenerated from fresh results:
  - `robustness_case_metrics.csv`
  - `robustness_camera_metrics.csv`
  - `robustness_summary_by_planes.csv`
  - `noise_case006_metrics.csv`
- new manuscript-output artifacts:
  - `paper_table_robustness.csv`
  - `paper_table_noise.csv`
  - `robustness_ray_rmse_by_case.pdf`
  - `noise_case006_sensitivity.pdf`
  - `run_manifest.json`
  - `paper_integration_checklist.md`
  - `synthetic_paper_results.ipynb`

### Definition of Done (verifiable conditions with commands)
- all result JSONs in the fresh rerun set have `used_bootstrap_cache == false`
- `run_precalibration_check` is used by `MockBase`, so logs no longer show fallback caused by missing method
- robustness aggregation CSV contains 29 rows or documented failures with matching failure JSON entries
- noise aggregation CSV contains 9 rows for sigma values `[0.00, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00]`
- manuscript tables and figures exist and are non-empty
- no files under `modules/camera_calibration/wand_calibration/` were edited

### Must Have
- archive stale results before rerun
- delete runtime cache files before each run
- isolate `sigma=0.0` noise cache from robustness cache
- update all three launchers to completion-order future handling
- preserve current metrics schema in `_extract_metrics`
- generate manuscript outputs from aggregate CSVs, not from ad hoc manual analysis
- regenerate the notebook documenting execution, analysis, and plotting

### Must NOT Have
- no algorithm edits under `modules/camera_calibration/wand_calibration/`
- no refactor of harness architecture beyond targeted fixes
- no new synthetic cases
- no notebook-only post-processing dependency as the primary path
- no notebook as the only source of truth for result generation
- no human-only verification steps

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after with lightweight pre-flight verification and post-run integrity checks
- QA policy: every task includes exact agent-executed checks
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy

### Parallel Execution Waves
Wave 1: cleanup + harness logic fixes
- stale-result archive
- `MockBase.run_precalibration_check`
- runtime cache deletion + sigma-zero isolation

Wave 2: launcher fixes + pre-flight verification
- `run_robustness.py`
- `run_noise_sweep.py`
- `run_all_tests.py`
- pre-flight verification

Wave 3: bulk execution + manuscript outputs
- full robustness rerun
- full noise rerun
- manuscript-output generator
- notebook regeneration
- final artifact generation

### Dependency Matrix
- Task 1 blocks all reruns.
- Tasks 2 and 3 block pre-flight verification and bulk reruns.
- Task 4 blocks stable bulk execution.
- Task 5 blocks manuscript-ready deliverables.
- Tasks 6 and 7 require Tasks 1-4 complete.
- Task 8 requires Tasks 6 and 7 complete.
- Task 9 requires Tasks 5, 6, 7, and 8 complete.

### Agent Dispatch Summary
- Wave 1: 3 tasks → quick / unspecified-high
- Wave 2: 2 tasks → quick
- Wave 3: 4 tasks → unspecified-high / writing

## TODOs

- [ ] 1. Archive invalid prior results and clear stale caches

  **What to do**:
  - Move the current `J:\Refraction_test\test_results` directory to a timestamped archive such as `J:\Refraction_test\test_results_archived_YYYYMMDD_HHMMSS`.
  - Recreate a fresh `J:\Refraction_test\test_results` root.
  - Remove stale cache files from source case directories if present:
    - `J:\Refraction_test\case_*\bootstrap_cache.json`
    - `J:\Refraction_test\case_*\bundle_cache.json`
  - Do not alter any source CSV inputs, camera files, or case metadata.

  **Must NOT do**:
  - Must not delete case directories.
  - Must not modify any file under the repo algorithm directory.
  - Must not keep old cached-run outputs mixed with new paper outputs.

  **Recommended Agent Profile**:
  - Category: `quick` — filesystem cleanup with clear boundaries
  - Skills: `[]`
  - Omitted: no special skill required

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4, 6, 7

  **References**:
  - Existing stale artifacts observed under `J:\Refraction_test\test_results\cache_inputs\...`
  - Current invalid cached outputs include `bootstrap_cache.json`, `bundle_cache.json`, `triangulation_report.json`

  **Acceptance Criteria**:
  - [ ] Fresh `J:\Refraction_test\test_results` exists
  - [ ] Old `test_results` contents are not present in the new path
  - [ ] Source case cache files are absent before reruns

  **QA Scenarios**:
  ```
  Scenario: Archive completes cleanly
    Tool: Bash
    Steps: List archived dir and fresh test_results dir after cleanup
    Expected: Archived dir exists; fresh test_results is recreated and empty except expected subdirs
    Evidence: .sisyphus/evidence/task-1-archive.txt

  Scenario: Source case caches removed
    Tool: Bash
    Steps: List `J:\Refraction_test\case_*\bootstrap_cache.json` and `bundle_cache.json`
    Expected: No matches remain
    Evidence: .sisyphus/evidence/task-1-source-cache-check.txt
  ```

  **Commit**: NO | Message: `` | Files: external `J:` paths only

- [x] 2. Add `run_precalibration_check` to `MockBase`

  **What to do**:
  - Edit `J:\Refraction_test\test_script\run_calibration_worker.py`.
  - Add `MockBase.run_precalibration_check(self, wand_length=1.0, init_focal_length=5000, callback=None, **kwargs)` immediately after the constructor.
  - The method must supply the interface expected by `refractive_bootstrap.select_best_pair_via_precalib()`.
  - Implement a fast pinhole precalibration path sufficient to populate `self.per_frame_errors` as `{fid: {'cam_errors': {cid: float}}}` and return `(ret, msg, result)`.
  - The method may use existing imported dependencies in the harness (`cv2`, `numpy`, `scipy`) but must not import or modify core calibration modules.
  - Use the existing `wand_points`, `camera_settings`, `image_size`, and `dist_coeff_num` already on `MockBase`.

  **Must NOT do**:
  - Must not import from `modules.camera_calibration.wand_calibration.*`
  - Must not change `MockBase.__init__` signature
  - Must not change result schema outside `per_frame_errors`

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — non-trivial numeric compatibility method
  - Skills: `[]`
  - Omitted: no refactor skill

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 7

  **References**:
  - `J:\Refraction_test\test_script\run_calibration_worker.py:411-455` — current `MockBase`
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:27-145` — caller expectations
  - `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:1938` — where the path is used
  - `modules/camera_calibration/wand_calibration/wand_calibrator.py:2158-2315` — real signature and behavior pattern to mirror, without importing it

  **Acceptance Criteria**:
  - [ ] `MockBase` exposes `run_precalibration_check`
  - [ ] Method returns a 3-tuple on success and failure paths
  - [ ] `self.per_frame_errors` is populated with numeric per-camera errors on a valid case
  - [ ] Robustness/noise logs no longer show fallback due to missing `run_precalibration_check`

  **QA Scenarios**:
  ```
  Scenario: Method exists and runs on a real case
    Tool: Bash
    Steps: `conda run -n OpenLPT python -c "import sys; sys.path.insert(0, r'J:\Refraction_test\test_script'); from run_calibration_worker import load_case_inputs; inputs = load_case_inputs(r'J:\Refraction_test\case_001'); mb = inputs['mock_base']; ret,msg,res = mb.run_precalibration_check(wand_length=10.0, init_focal_length=inputs['focal_px']); print(ret, len(mb.per_frame_errors), type(msg).__name__)"`
    Expected: `ret` is truthy or documented-false with structured message, and method exists without AttributeError
    Evidence: .sisyphus/evidence/task-2-precalib-check.txt

  Scenario: Fallback due to missing method is gone
    Tool: Bash
    Steps: Run one smoke case and grep the log for `run_precalibration_check is unavailable`
    Expected: No match
    Evidence: .sisyphus/evidence/task-2-no-missing-method.txt
  ```

  **Commit**: NO | Message: `` | Files: external `J:` path only

- [x] 3. Fix runtime cache handling and isolate `sigma=0.0` noise runs

  **What to do**:
  - Edit `J:\Refraction_test\test_script\run_calibration_worker.py`.
  - Replace the cache-mirroring block in `prepare_runtime_case_dir` so runtime cache files are deleted instead of copied.
  - Change the noise-path branch so **all** noise runs, including `sigma_px == 0.0`, use a dedicated noise cache directory, e.g. `cache_inputs/case_006/noise_sigma0p00/`.
  - Preserve returned dict keys (`cache_dir`, `out_path`, `log_dir`, `bootstrap_cache_exists`, `bundle_cache_exists`).
  - Ensure returned cache booleans reflect the new clean-run policy: always `False` before run dispatch.

  **Must NOT do**:
  - Must not leave `sigma=0.0` sharing robustness cache path
  - Must not remove directory creation logic
  - Must not change function signature

  **Recommended Agent Profile**:
  - Category: `quick` — isolated function edit
  - Skills: `[]`
  - Omitted: no special skill required

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 7

  **References**:
  - `J:\Refraction_test\test_script\run_calibration_worker.py:822-913`
  - Current branch condition at lines `867-874`
  - Current cache mirroring at lines `885-905`
  - Current results flags consumed at `987-988` and analogous noise path lines later in the file

  **Acceptance Criteria**:
  - [ ] No `shutil.copy2` remains in `prepare_runtime_case_dir`
  - [ ] `sigma=0.0` noise runs map to `noise_sigma0p00` path
  - [ ] Runtime cache booleans are `False` on fresh dispatch

  **QA Scenarios**:
  ```
  Scenario: Runtime caches are deleted, not mirrored
    Tool: Bash
    Steps: Plant fake cache files in runtime cache dir; call function again
    Expected: Files are removed; return booleans are False
    Evidence: .sisyphus/evidence/task-3-cache-delete.txt

  Scenario: Sigma zero gets its own cache dir
    Tool: Bash
    Steps: Call prepare_runtime_case_dir(case_006, result_root, run_type='noise', sigma_px=0.0)
    Expected: Returned cache_dir path ends with `noise_sigma0p00`
    Evidence: .sisyphus/evidence/task-3-sigma-zero.txt
  ```

  **Commit**: NO | Message: `` | Files: external `J:` path only

- [x] 4. Replace submission-order future handling with completion-order handling in all launchers

  **What to do**:
  - Edit these files:
    - `J:\Refraction_test\test_script\run_robustness.py`
    - `J:\Refraction_test\test_script\run_noise_sweep.py`
    - `J:\Refraction_test\test_script\run_all_tests.py`
  - Import `as_completed` from `concurrent.futures` in each file.
  - Replace `for fut in futures:` loops with `for fut in as_completed(futures):`.
  - Preserve current result writing and console status formatting.
  - Keep `ProcessPoolExecutor(..., mp_context=get_context("spawn"))` unchanged.
  - Add per-future timeout only if needed by the implementation agent; it is optional in this plan because the user’s core concern is correct completion-order progress.

  **Must NOT do**:
  - Must not alter result schemas
  - Must not add retry logic unrelated to the iteration-order bug
  - Must not remove smoke gates

  **Recommended Agent Profile**:
  - Category: `quick`
  - Skills: `[]`
  - Omitted: no special skill required

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocked By: 1 | Blocks: 6, 7

  **References**:
  - `run_robustness.py:404-439`
  - `run_noise_sweep.py:280-319`
  - `run_all_tests.py:189-220`, `253-286`

  **Acceptance Criteria**:
  - [ ] All launcher files import `as_completed`
  - [ ] No `for fut in futures:` remains in any launcher
  - [ ] Dry-run mode still works in all launchers

  **QA Scenarios**:
  ```
  Scenario: Robustness launcher uses completion-order futures
    Tool: Bash
    Steps: Grep `run_robustness.py` for `as_completed` and `for fut in futures:`
    Expected: `as_completed` present; old loop absent
    Evidence: .sisyphus/evidence/task-4-robustness-loop.txt

  Scenario: Noise and combined launchers also updated
    Tool: Bash
    Steps: Repeat grep checks on `run_noise_sweep.py` and `run_all_tests.py`
    Expected: same as above
    Evidence: .sisyphus/evidence/task-4-other-launchers.txt

  Scenario: Dry-run preserved
    Tool: Bash
    Steps: run `python run_robustness.py --dry-run`, `python run_noise_sweep.py --dry-run`, `python run_all_tests.py --dry-run`
    Expected: exit code 0 for each and no execution side effects
    Evidence: .sisyphus/evidence/task-4-dryrun.txt
  ```

  **Commit**: NO | Message: `` | Files: external `J:` paths only

- [x] 5. Add manuscript-output generator script

  **What to do**:
  - Create a new script in `J:\Refraction_test\test_script`, named `generate_manuscript_outputs.py`.
  - Input files:
    - `J:\Refraction_test\test_results\robustness_case_metrics.csv`
    - `J:\Refraction_test\test_results\robustness_summary_by_planes.csv`
    - `J:\Refraction_test\test_results\noise_case006_metrics.csv`
  - Output files:
    - `J:\Refraction_test\test_results\paper_table_robustness.csv`
    - `J:\Refraction_test\test_results\paper_table_noise.csv`
    - `J:\Refraction_test\test_results\figures\robustness_ray_rmse_by_case.pdf`
    - `J:\Refraction_test\test_results\figures\noise_case006_sensitivity.pdf`
    - `J:\Refraction_test\test_results\run_manifest.json`
    - `J:\Refraction_test\test_results\paper_integration_checklist.md`
  - The script must derive manuscript outputs from the existing aggregate CSV schema, not by re-running calibration.
  - The run manifest must include:
    - timestamp
    - script paths used
    - current metric columns used
    - counts of robustness and noise rows
    - whether any failures remain
    - path list of generated manuscript artifacts
  - The checklist must summarize pass/fail items for manuscript inclusion.

  **Must NOT do**:
  - Must not require Jupyter as the primary execution path
  - Must not change `_extract_metrics` schema just to make tables
  - Must not depend on manual spreadsheet editing

  **Recommended Agent Profile**:
  - Category: `writing` — deterministic post-processing + report artifact generation
  - Skills: `[]`
  - Omitted: no notebook skill

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocked By: 6, 7 | Blocks: 8

  **References**:
  - Existing robustness aggregate columns at `run_robustness.py:163-193`
  - Existing summary-by-planes columns at `run_robustness.py:308-326`
  - Existing noise aggregate columns at `run_noise_sweep.py:148-179`
  - Existing metrics source at `run_calibration_worker.py:686-738`

  **Acceptance Criteria**:
  - [ ] Script runs in one command and exits 0 on valid aggregate CSVs
  - [ ] All six manuscript artifacts are generated and non-empty
  - [ ] `paper_table_robustness.csv` and `paper_table_noise.csv` use only fresh rerun data
  - [ ] `run_manifest.json` contains row counts and generated artifact paths

  **QA Scenarios**:
  ```
  Scenario: Manuscript generator runs end-to-end
    Tool: Bash
    Steps: `python J:\Refraction_test\test_script\generate_manuscript_outputs.py`
    Expected: exit 0 and all target files created
    Evidence: .sisyphus/evidence/task-5-manuscript-script.txt

  Scenario: Manifest matches aggregates
    Tool: Bash
    Steps: Read manifest JSON and compare stored row counts with CSV row counts
    Expected: Counts match exactly
    Evidence: .sisyphus/evidence/task-5-manifest-check.txt
  ```

  **Commit**: NO | Message: `` | Files: external `J:` path only

- [x] 6. Recreate the notebook for running, analysis, and plotting

  **What to do**:
  - Create `J:\Refraction_test\test_script\synthetic_paper_results.ipynb`.
  - The notebook must be a companion artifact to the scripts, not the primary execution path.
  - Required notebook sections:
    1. overview / purpose
    2. environment and path setup
    3. how to run pre-flight checks
    4. how to run robustness wave
    5. how to run noise sweep
    6. how to rerun failed jobs / resume
    7. how to load aggregate CSVs
    8. how manuscript tables are derived
    9. how manuscript plots are generated
    10. where outputs are saved
  - The notebook must reference the actual scripts in `J:\Refraction_test\test_script` and the actual outputs in `J:\Refraction_test\test_results`.
  - The notebook must show result analysis and plotting from saved CSVs/results, not by embedding ad hoc unreproducible logic.

  **Must NOT do**:
  - Must not become the only way to generate final manuscript outputs
  - Must not rerun calibration implicitly on notebook open
  - Must not hardcode obsolete paths or deleted plan references

  **Recommended Agent Profile**:
  - Category: `writing`
  - Skills: `[]`
  - Omitted: no notebook-only workflow

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocked By: 5, 6, 7? NO — can be created after script interfaces stabilize, before final reruns if desired | Blocks: 9

  **References**:
  - `J:\Refraction_test\test_script\run_robustness.py`
  - `J:\Refraction_test\test_script\run_noise_sweep.py`
  - `J:\Refraction_test\test_script\run_all_tests.py`
  - `J:\Refraction_test\test_results\robustness_case_metrics.csv`
  - `J:\Refraction_test\test_results\noise_case006_metrics.csv`

  **Acceptance Criteria**:
  - [ ] Notebook exists at the required path
  - [ ] Notebook documents run commands, result loading, table derivation, and plot generation
  - [ ] Notebook points to the script-based output generator as the canonical reproducible path

  **QA Scenarios**:
  ```
  Scenario: Notebook file exists and has required sections
    Tool: Bash
    Steps: Inspect notebook JSON for section headings / markdown cells
    Expected: All required sections present
    Evidence: .sisyphus/evidence/task-6-notebook-sections.txt

  Scenario: Notebook references actual scripts and outputs
    Tool: Bash
    Steps: Search notebook JSON for `run_robustness.py`, `run_noise_sweep.py`, `robustness_case_metrics.csv`, and `noise_case006_metrics.csv`
    Expected: All references present
    Evidence: .sisyphus/evidence/task-6-notebook-paths.txt
  ```

  **Commit**: NO | Message: `` | Files: external `J:` path only

- [ ] 7. Run full robustness campaign

  **What to do**:
  - Run pre-flight verification before launch:
    - confirm `J:\Refraction_test\test_results` is the fresh rerun root, not an archived directory
    - confirm no source-case `bootstrap_cache.json` or `bundle_cache.json` remain under `J:\Refraction_test\case_*`
    - confirm `MockBase` exposes `run_precalibration_check`
    - confirm launchers use `as_completed`
  - If any pre-flight check fails, rerun Task 1 and repeat the verification before launching the full campaign.
  - Run full robustness campaign across 29 runnable cases.
  - Save logs, per-case JSON results, failure JSON, and regenerated aggregate CSVs.
  - Launch the full campaign in a detached tmux session via `interactive_bash`; do not run it in a blocking shell call.

  **Execution Mandate**:
  - These full reruns are long-running and must not be launched with short blocking timeouts.
  - Use `interactive_bash` with a named tmux session for the robustness campaign.
  - Use `C:\Users\tan_s\miniconda3\envs\OpenLPT\python.exe` for all Python commands unless the OpenLPT environment is already confirmed active.
  - Poll the tmux session for progress/completion instead of restarting the run.

  **Must NOT do**:
  - Must not rerun against archived outputs
  - Must not launch the full run through the standard `Bash` tool with a blocking timeout
  - Must not restart the campaign because of avoidable tool timeout interruption

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Skills: `[]`
  - Omitted: none

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocked By: 1, 2, 3, 4 | Blocks: 5, 9

  **References**:
  - `run_robustness.py:380-469`

  **Acceptance Criteria**:
  - [ ] Pre-flight verification passes before launch
  - [ ] `robustness_case_metrics.csv` exists after run
  - [ ] `failures_robustness.json` is empty or explicitly documents remaining failures
  - [ ] Result JSONs show `used_bootstrap_cache == false`

  **QA Scenarios**:
  ```
  Scenario: Pre-flight verification passes
    Tool: Bash
    Steps: verify fresh `test_results`, verify no source-case caches remain, verify `MockBase.run_precalibration_check` exists, verify launchers import `as_completed`
    Expected: all checks pass before campaign launch
    Evidence: .sisyphus/evidence/task-7-preflight.txt

  Scenario: Robustness campaign launches without blocking timeout risk
    Tool: interactive_bash
    Steps: create detached tmux session; launch `C:\Users\tan_s\miniconda3\envs\OpenLPT\python.exe J:\Refraction_test\test_script\run_robustness.py`; poll tmux until completion
    Expected: campaign runs to completion without being killed by a short API timeout
    Evidence: .sisyphus/evidence/task-7-robustness-run.txt

  Scenario: Robustness CSV row count
    Tool: Bash
    Steps: count rows in `robustness_case_metrics.csv`
    Expected: 29 data rows or documented failures present in `failures_robustness.json`
    Evidence: .sisyphus/evidence/task-7-robustness-count.txt

  Scenario: Robustness results are cache-free
    Tool: Bash
    Steps: inspect result JSON files for `used_bootstrap_cache`
    Expected: every fresh result JSON reports `used_bootstrap_cache == false`
    Evidence: .sisyphus/evidence/task-7-cache-free.txt
  ```

  **Commit**: NO | Message: `` | Files: generated artifacts only

- [ ] 8. Run fresh noise campaign on `case_006`

  **What to do**:
  - Reuse the same pre-flight verification standard as Task 7 before launch.
  - Run noise sweep across all 9 sigma levels on `case_006` using the fixed launcher.
  - Save per-sigma JSONs, logs, failure JSON, and regenerated `noise_case006_metrics.csv`.
  - Launch the full noise sweep in a detached tmux session via `interactive_bash`; do not run it in a blocking shell call.

  **Execution Mandate**:
  - This full noise sweep is long-running and must not be launched with short blocking timeouts.
  - Use `interactive_bash` with a named tmux session for the noise campaign.
  - Use `C:\Users\tan_s\miniconda3\envs\OpenLPT\python.exe` for all Python commands unless the OpenLPT environment is already confirmed active.
  - Poll the tmux session for progress/completion instead of restarting the run.

  **Must NOT do**:
  - Must not reuse robustness cache path for `sigma=0.0`
  - Must not skip failed sigmas silently
  - Must not launch the full run through the standard `Bash` tool with a blocking timeout
  - Must not restart the campaign because of avoidable tool timeout interruption

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Skills: `[]`
  - Omitted: none

  **Parallelization**: Can Parallel: YES with Task 7 if resources allow | Wave 3 | Blocked By: 1, 2, 3, 4 | Blocks: 5, 9

  **References**:
  - `run_noise_sweep.py:256-343`

  **Acceptance Criteria**:
  - [ ] `noise_case006_metrics.csv` exists with 9 data rows
  - [ ] `failures_noise.json` is empty or documents remaining failures explicitly
  - [ ] `sigma0p00` results have dedicated cache path
  - [ ] Result JSONs show `used_bootstrap_cache == false`

  **QA Scenarios**:
  ```
  Scenario: Noise sweep completes all sigmas
    Tool: interactive_bash
    Steps: create detached tmux session; launch `C:\Users\tan_s\miniconda3\envs\OpenLPT\python.exe J:\Refraction_test\test_script\run_noise_sweep.py`; poll tmux until completion
    Expected: 9 sigma outputs produced
    Evidence: .sisyphus/evidence/task-8-noise-run.txt

  Scenario: Noise CSV row count
    Tool: Bash
    Steps: count rows in `noise_case006_metrics.csv`
    Expected: 9 data rows
    Evidence: .sisyphus/evidence/task-8-noise-count.txt

  Scenario: Noise results are cache-free
    Tool: Bash
    Steps: inspect noise result JSON files for `used_bootstrap_cache` and verify `sigma0p00` path isolation
    Expected: every fresh noise result JSON reports `used_bootstrap_cache == false`, and sigma-zero output is isolated from robustness cache paths
    Evidence: .sisyphus/evidence/task-8-cache-free.txt
  ```

  **Commit**: NO | Message: `` | Files: generated artifacts only

- [ ] 9. Generate manuscript artifacts and final reproducibility package

  **What to do**:
  - Run `generate_manuscript_outputs.py` after Tasks 7 and 8 complete.
  - Verify the new tables, figures, manifest, and checklist are all present.
  - Verify the notebook is present and aligned with the final script/output paths.
  - Ensure figures and tables are based only on fresh rerun outputs.

  **Must NOT do**:
  - Must not mix archived stale data into the final manuscript outputs
  - Must not leave undocumented failures out of the manifest/checklist

  **Recommended Agent Profile**:
  - Category: `writing`
  - Skills: `[]`
  - Omitted: none

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocked By: 5, 6, 7, 8

  **References**:
  - Outputs defined in Task 5

  **Acceptance Criteria**:
  - [ ] all manuscript artifacts exist and are non-empty
  - [ ] manifest row counts match aggregate CSVs
  - [ ] checklist explicitly reports success/failure status for robustness and noise campaigns
  - [ ] notebook exists and references the final artifact paths

  **QA Scenarios**:
  ```
  Scenario: All manuscript outputs exist
    Tool: Bash
    Steps: list each required output file and check non-zero file size
    Expected: every required artifact exists and is non-empty
    Evidence: .sisyphus/evidence/task-9-artifacts.txt

  Scenario: Manifest consistency
    Tool: Bash
    Steps: compare manifest row counts with CSV row counts and failure JSON presence
    Expected: exact match
    Evidence: .sisyphus/evidence/task-9-manifest-consistency.txt
  ```

  **Commit**: NO | Message: `` | Files: generated artifacts only

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- External `J:` test scripts are outside the git repo, so implementation work should not assume normal repo commits for those files.
- If the executor wants versioned traceability, mirror the final external scripts into a repo-side reference location only if explicitly approved later. For this plan, no repo commit is required.

## Success Criteria
- Harness reruns are fresh and cache-free.
- Robustness and noise campaigns complete with regenerated aggregate CSVs.
- Manuscript tables/figures/manifest/checklist are generated from fresh results only.
- No core algorithm file is edited.

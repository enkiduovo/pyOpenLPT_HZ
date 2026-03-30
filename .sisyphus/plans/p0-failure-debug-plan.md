# P0 Failure Debug Plan

## TL;DR
> **Summary**: Build a closed-loop debug campaign that first proves why the 7 P0 failures collapse, then hardens the bootstrap if the geometry is still recoverable.
> **Deliverables**: failure evidence matrix, P0 telemetry, controlled ablation runner, bootstrap hardening patch, regression tests, cache-free rerun, final diagnosis note.
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: evidence matrix → ablation runner/tests → bootstrap hardening → full rerun

## Context
### Original Request
Analyze why the 7 robustness cases failed and determine whether the camera setup is ill-posed or the code is too brittle to handle it; if the code is insufficient, improve it until the issue is solved.

### Interview Summary
- Seven cases fail at P0 with reprojection errors in the `1e5`–`6e5` px range.
- The selected baselines are tiny (`0.25`–`1.76` mm) compared with the 50 mm warning threshold.
- Some failures also show severe workspace collapse (`n_valid=1` and huge `reject_vis`), but not every failure is purely cramped.
- Oracle’s guidance: classify first using conditioning evidence, then run near-ground-truth / threshold-sensitivity ablations to separate geometry-limited cases from bootstrap brittleness.
- Metis’s guardrails: do not rely on log-grep alone, add tests before fixes, and make the debug loop finite and automated.
- New workspace policy: new scripts/results for this plan may live under `J:\Refraction_test\test_script` and `J:\Refraction_test\test_results`.

### Metis Review (gaps addressed)
- Added an explicit evidence/classification stage before any fix.
- Added TDD-backed regression tasks before bootstrap edits.
- Added an ablation runner and a finite decision gate so the loop cannot run forever.
- Added an explicit outcome for unrecoverable cases: `INSUFFICIENT_GEOMETRY`, not silent `[P0 FAIL]`.

## Work Objectives
### Core Objective
Produce solid, reproducible evidence for each of the 7 failures and either recover them with bootstrap improvements or classify them as genuinely ill-posed with explicit diagnostics.

### Deliverables
- Failure evidence matrix for all 7 cases plus passing comparisons.
- P0 telemetry fields for baseline, pair choice, inliers, scale factor, triangulation health, and residual summaries.
- Controlled ablation runner for forced pairs, threshold sweeps, and near-ground-truth seeding.
- Regression tests proving the bootstrap survives the recoverable failure modes.
- Bootstrap hardening patch if the ablations show algorithmic brittleness.
- Fresh cache-free 29-case robustness rerun and 9-level noise sweep rerun.
- Final diagnosis note for manuscript use.

### Definition of Done (verifiable conditions with commands)
- Every one of the 7 failed cases has a written verdict backed by logs and ablation evidence.
- Recoverable cases run through `RefractiveWandCalibrator.calibrate()` without `[P0 FAIL]`.
- Geometry-limited cases fail early with explicit diagnostics, not catastrophic reprojection blow-up.
- All new bootstrap tests pass under `pytest`.
- Fresh reruns report `used_bootstrap_cache == false` and `used_bundle_cache == false`.

### Must Have
- No cache reuse in any debug or rerun path.
- No hardcoded pair choice in the final evidence runner.
- No threshold loosening without an evidence-backed reason.
- Every code change must be paired with a failing regression test first.
- All new debug/test code for this plan may live under `J:\Refraction_test\test_script`.
- All generated outputs, rerun artifacts, logs, and evidence for this plan may live under `J:\Refraction_test\test_results`.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Do not hide failures by simply increasing thresholds.
- Do not accept log-grep as proof of numerical correctness.
- Do not modify the core calibration model outside the bootstrap/debug boundary.
- Do not leave any case in an ambiguous state after the loop finishes.
- Do not create new scripts or results outside `J:\Refraction_test\test_script` and `J:\Refraction_test\test_results` for this plan.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: **TDD for bootstrap fixes**, tests-after for evidence-only work.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `J:\Refraction_test\test_results\logs\p0-debug\*.log`, `J:\Refraction_test\test_results\p0-debug\*.json`, and planning notes in `.sisyphus/evidence/p0-debug/`.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave when possible; keep shared dependencies in Wave 1.

Wave 1: evidence collection + P0 telemetry + test scaffolding
Wave 2: ablation runner + controlled classification runs
Wave 3: bootstrap hardening fixes + regression reruns

### Dependency Matrix (full, all tasks)
- Task 1 feeds Tasks 2-4.
- Task 2 feeds Tasks 3-7.
- Task 3 must exist before any bootstrap fix commits.
- Task 4 determines whether Task 5 is a fix or an explicit geometry-classification change.
- Task 6 must run after Task 5 and before final diagnosis.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 3 tasks → deep / unspecified-high
- Wave 2 → 2 tasks → deep / quick
- Wave 3 → 2 tasks → unspecified-high / writing

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Build failure evidence matrix

  **What to do**: Extract a per-case table for the 7 failures and a small passing baseline set. Capture `case_meta.json`, selected pair, `n_valid`, `reject_vis`, baseline, P0 reprojection mean, initial/final BA cost, inlier counts, and whether the failure looks geometry-limited or algorithm-limited. Write the summarizer under `J:\Refraction_test\test_script` and its outputs under `J:\Refraction_test\test_results`.

  **Must NOT do**: Do not modify code; do not infer root cause from one metric alone.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: requires cross-case pattern analysis.
  - Skills: `[]` — no external library needed.
  - Omitted: `quick` — too much evidence to fit a trivial pass.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [2, 3, 4, 5] | Blocked By: []

  **References**:
  - Logs: `J:\Refraction_test\test_results\logs\robustness\case_012.log`, `case_015.log`, `case_019.log`, `case_023.log`, `case_027.log`, `case_028.log`, `case_029.log` — ground truth failure traces.
  - Case metadata: `J:\Refraction_test\case_*/case_meta.json` — geometry, FOV, visibility, camera layout (legacy input only).
  - Comparison: `J:\Refraction_test\test_results\per_case\robustness\case_001.json` — healthy baseline behavior.

  **Acceptance Criteria**:
  - [ ] The matrix contains all 7 failures plus at least 3 passing comparisons.
  - [ ] Each row has a verdict backed by a concrete metric set.
  - [ ] A repeatable classification rule is recorded (geometry-limited vs algorithm-limited).

  **QA Scenarios**:
  ```
  Scenario: Happy path classification
    Tool: Bash
    Steps: Run the evidence summarizer on the 7 failing case logs and the selected passing comparison logs.
    Expected: A single report file lists every case with baseline, selected pair, n_valid, reject_vis, and verdict.
    Evidence: J:\Refraction_test\test_results\p0_debug\failure_matrix.md

  Scenario: Missing input handling
    Tool: Bash
    Steps: Point the summarizer at a nonexistent case log.
    Expected: The command fails with a clear missing-file error and no partial report is emitted.
    Evidence: J:\Refraction_test\test_results\p0_debug\failure_matrix_missing_input.txt
  ```

  **Commit**: NO

- [x] 2. Add P0 telemetry and failure reasons

  **What to do**: Instrument `refractive_bootstrap.py` so P0 logs and reports selected pair, baseline, E-inliers, pose-inliers, cheirality ratio, valid inlier count, median triangulation length, scale factor sanity, and an explicit failure reason when geometry is insufficient or the solve becomes numerically unstable. Persist reports under `J:\Refraction_test\test_results`.

  **Must NOT do**: Do not change calibration math yet; only add diagnostics and safe guards.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: touches core bootstrap logic and reporting.
  - Skills: `[]` — no external library needed.
  - Omitted: `quick` — too risk-sensitive.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [4, 5, 6, 7] | Blocked By: [1]

  **References**:
  - `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:1937-1967` — pair selection and P0 entry.
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:268-350` — E-matrix, pose recovery, scale recovery.
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:430-519` — residuals and BA gating.
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:606-681` — diagnostics and hard failure threshold.

  **Acceptance Criteria**:
  - [ ] Every P0 run emits a structured diagnostics block with the new fields.
  - [ ] Geometry-limited runs return a specific failure reason instead of only a generic reprojection explosion.
  - [ ] Healthy case `case_001` still passes with cache disabled and unchanged metrics.

  **QA Scenarios**:
  ```
  Scenario: Healthy case diagnostics
    Tool: Bash
    Steps: Run `case_001` through the debug harness after instrumentation.
    Expected: P0 passes, diagnostics fields are present, and baseline/reprojection stay healthy.
    Evidence: J:\Refraction_test\test_results\p0_debug\case_001_diagnostics.log

  Scenario: Failed case diagnostics
    Tool: Bash
    Steps: Run `case_023` through the same harness.
    Expected: The report records the explicit failure reason plus the conditioning metrics.
    Evidence: J:\Refraction_test\test_results\p0_debug\case_023_diagnostics.log
  ```

  **Commit**: YES | Message: `fix(bootstrap): add structured P0 diagnostics and failure reasons` | Files: `modules/camera_calibration/wand_calibration/refractive_bootstrap.py`

- [x] 3. Build regression tests and ablation harness

  **What to do**: Add bootstrap regression tests and a deterministic ablation runner that can replay the failing cases under forced pair selection, threshold sweeps, and near-ground-truth seeding. Put all runner code under `J:\Refraction_test\test_script`. Tests must fail before bootstrap changes and must not depend on any bootstrap cache. All generated outputs must be written under `J:\Refraction_test\test_results`.

  **Must NOT do**: Do not hardcode one pair or one camera layout; do not rely on the J: cache.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: requires test scaffolding plus a reusable runner.
  - Skills: `[]` — no external library needed.
  - Omitted: `quick` — needs careful coverage.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [4, 5, 6, 7] | Blocked By: [2]

  **References**:
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:267-350` — the exact P0 failure-sensitive path to cover.
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:667-681` — hard-fail gate to exercise.
  - `J:\Refraction_test\test_script` — destination for new ablation/debug runners and regression tests.
  - `J:\Refraction_test\test_script\run_robustness.py` — reference and execution target.

  **Acceptance Criteria**:
  - [ ] There is at least one failing regression test that reproduces the bad P0 behavior before the fix.
  - [ ] The ablation runner can force alternate pairs and threshold settings deterministically.
  - [ ] The runner writes per-configuration JSON evidence with `used_bootstrap_cache=false`.

  **QA Scenarios**:
  ```
  Scenario: Red-phase regression
    Tool: Bash
    Steps: Run the new bootstrap tests before the fix lands.
    Expected: The test reproducing the failure mode fails for the right reason.
    Evidence: J:\Refraction_test\test_results\p0_debug\bootstrap_red_phase.txt

  Scenario: Deterministic ablation run
    Tool: Bash
    Steps: Run the ablation harness on case_012 and case_023 with forced alternate pairs and a threshold sweep.
    Expected: Each configuration produces a JSON result and log entry.
    Evidence: J:\Refraction_test\test_results\p0_debug\ablation_case_012.json
  ```

  **Commit**: YES | Message: `test(bootstrap): add regression coverage and ablation harness` | Files: `tests/*`

- [x] 4. Classify the 7 failures with controlled ablations

  **What to do**: Run the ablation matrix and classify each case using explicit evidence: best pair vs forced alternative pair, threshold sensitivity, near-ground-truth seed sensitivity, and whether the solve remains bad even with robust settings. Store outputs under `J:\Refraction_test\test_results`.

  **Must NOT do**: Do not accept a guess; every verdict must be supported by at least two independent signals.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: comparisons across multiple dimensions.
  - Skills: `[]` — no external library needed.
  - Omitted: `quick` — too many moving pieces.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [5, 6] | Blocked By: [2, 3]

  **References**:
  - `J:\Refraction_test\test_results\logs\robustness\case_*.log` — baseline behavior.
  - `J:\Refraction_test\test_results\per_case\robustness\case_*.json` — run-level outputs.
  - `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:1937-1967` — pair selection entrypoint.

  **Acceptance Criteria**:
  - [ ] Each of the 7 failures is labeled either recoverable or geometry-limited.
  - [ ] Recoverable cases show a clear improvement path under at least one controlled ablation.
  - [ ] Geometry-limited cases remain bad even after robust pair/seed/threshold sweeps.

  **QA Scenarios**:
  ```
  Scenario: Recoverable-case proof
    Tool: Bash
    Steps: Replay a failing case under the best ablation setting found.
    Expected: The metrics materially improve relative to the baseline failure.
    Evidence: J:\Refraction_test\test_results\p0_debug\case_recovery_proof.json

  Scenario: Geometry-limit proof
    Tool: Bash
    Steps: Replay the worst constrained case under all ablation modes.
    Expected: It remains unstable or fails with explicit insufficient-geometry diagnostics.
    Evidence: J:\Refraction_test\test_results\p0_debug\case_geometry_limit.json
  ```

  **Commit**: NO

- [x] 5. Harden the bootstrap for recoverable cases

  **What to do**: If the ablations show algorithmic brittleness, implement the minimal fix set needed to recover the cases: safer pair ranking, degenerate-pair rejection, finite/NaN guards for scale, and more robust residual handling when triangulation is unstable. Keep updated scripts under `J:\Refraction_test\test_script` and outputs under `J:\Refraction_test\test_results`.

  **Must NOT do**: Do not rewrite the refractive model; do not tune thresholds blindly to hide failures.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: core algorithm fix with regression risk.
  - Skills: `[]` — no external library needed.
  - Omitted: `quick` — needs careful validation.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [6, 7] | Blocked By: [4]

  **References**:
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:268-350` — scale recovery and pair-dependent collapse point.
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:430-519` — BA residual construction and failure gate.
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:562-564` — behind-camera sentinel behavior.
  - `modules/camera_calibration/wand_calibration/refractive_bootstrap.py:667-681` — validation threshold that currently hard-fails.

  **Acceptance Criteria**:
  - [ ] Recoverable failures no longer end in catastrophic P0 reprojection blow-up.
  - [ ] Healthy case `case_001` remains stable and cache-free.
  - [ ] The fix is covered by the regression tests from Task 3.

  **QA Scenarios**:
  ```
  Scenario: Recovered failure case
    Tool: Bash
    Steps: Re-run a recoverable case after the fix lands.
    Expected: The run completes without `[P0 FAIL]` and produces finite metrics.
    Evidence: J:\Refraction_test\test_results\p0_debug\case_recovered_after_fix.json

  Scenario: No regression on healthy case
    Tool: Bash
    Steps: Re-run `case_001` after the fix.
    Expected: Metrics remain healthy and unchanged within tolerance.
    Evidence: J:\Refraction_test\test_results\p0_debug\case_001_post_fix.json
  ```

  **Commit**: YES | Message: `fix(bootstrap): harden pair selection and P0 stability checks` | Files: `modules/camera_calibration/wand_calibration/refractive_bootstrap.py`, `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py`

- [ ] 6. Rerun the full robustness and noise campaigns

  **What to do**: After fixes are in, rerun the 29-case robustness campaign and the 9-level noise sweep on `case_006` with 8 workers and no cache reuse. Store all run artifacts under `J:\Refraction_test\test_results`.

  **Must NOT do**: Do not reuse previous outputs; do not stop at partial success.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: orchestration and batch execution.
  - Skills: `[]` — no external library needed.
  - Omitted: `deep` — the analysis is already done.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [7] | Blocked By: [5]

  **References**:
  - `J:\Refraction_test\test_script` — destination for rerun wrappers and orchestrators.
  - `J:\Refraction_test\test_script\run_robustness.py` — execution target.
  - `J:\Refraction_test\test_script\run_noise_sweep.py` — execution target.

  **Acceptance Criteria**:
  - [ ] All reruns report `used_bootstrap_cache=false` and `used_bundle_cache=false`.
  - [ ] Each case writes a fresh JSON + log pair.
  - [ ] The noise sweep produces all 9 sigma levels for `case_006`.

  **QA Scenarios**:
  ```
  Scenario: Fresh robustness campaign
    Tool: Bash
    Steps: Run the robustness launcher with 8 workers and cache disabled.
    Expected: A complete 29-case result set is produced.
    Evidence: J:\Refraction_test\test_results\p0_debug\reruns\robustness\*

  Scenario: Fresh noise sweep
    Tool: Bash
    Steps: Run the noise sweep for case_006 with 9 sigma levels.
    Expected: All 9 sigma outputs are present and cache-free.
    Evidence: J:\Refraction_test\test_results\p0_debug\reruns\noise_case_006\*
  ```

  **Commit**: NO

- [ ] 7. Produce the final diagnosis package

  **What to do**: Summarize the final verdict for each of the 7 failures, document the exact fix set (if any), and produce a short debug note suitable for manuscript support.

  **Must NOT do**: Do not claim a geometry cause without the ablation evidence; do not claim a fix worked without the rerun evidence.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: final diagnosis note and summary.
  - Skills: `[]` — no external library needed.
  - Omitted: `deep` — evidence already exists.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [] | Blocked By: [6]

  **References**:
  - `J:\Refraction_test\test_results\p0_debug\*` — all evidence artifacts.
  - `J:\Refraction_test\test_results\p0_debug\reruns\robustness\*.json` — rerun outputs.
  - `J:\Refraction_test\test_results\p0_debug\reruns\robustness\*.log` — final logs.

  **Acceptance Criteria**:
  - [ ] Every failure has a final verdict and rationale.
  - [ ] The diagnosis package can be handed directly to manuscript work.
  - [ ] Any unresolved cases are explicitly marked as geometry-limited, not left ambiguous.

  **QA Scenarios**:
  ```
  Scenario: Final summary build
    Tool: Bash
    Steps: Aggregate the final evidence and rerun outputs into a diagnosis note.
    Expected: The note states which cases were recovered, which were geometry-limited, and why.
    Evidence: .sisyphus/evidence/p0-debug/final_diagnosis.md
  ```

  **Commit**: NO

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Use one commit per bootstrap fix.
- Keep the ablation runner and regression tests in the same change stream so each fix has a red/green proof.
- Do not bundle the final diagnosis note with algorithm changes.

## Success Criteria
- The 7 failures are either recovered or explicitly classified as insufficient geometry with evidence.
- No recoverable case remains unexplained.
- The rerun campaign is cache-free and reproducible.
- The final diagnosis can be reused in the manuscript with no further debugging.

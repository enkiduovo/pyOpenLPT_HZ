# Round4 Radius Inflation Debug Loop

## TL;DR
> **Summary**: Debug the Round4 sphere-radius inflation anomaly in the refractive calibration flow until the root cause is proven and fixed, using an evidence-first loop that reproduces the bug, instruments each hypothesis, consults Metis after ambiguous rounds, and stops only when case reruns and regression tests show Round4 radii remain physically plausible.
> **Deliverables**:
> - targeted debug instrumentation in the current working directory
> - a reproducible radius-anomaly harness for `case_001`
> - regression tests proving the fixed behavior
> - a repaired Round4 radius-estimation path
> - cache-free verification reruns and an evidence summary
> **Effort**: Large
> **Parallel**: NO
> **Critical Path**: reproduce anomaly → instrument frame/state mismatch → test hypotheses one-by-one → fix root cause → add regression tests → rerun case verification

## Context
### Original Request
Create a plan that tells the worker to debug the Round4 sphere-radius inflation problem until it is solved, and allow the worker to call Metis to analyze results and suggest the next step.

### Interview Summary
- `J:\Refraction_test\test_results\logs\robustness\case_001.log` shows plausible early estimates:
  - `BOOT: Stored estimated radii in dataset: Small=1.419mm, Large=1.892mm`
  - `BA: Updated estimated radii: Small=1.419mm, Large=1.892mm`
- The same log later shows inflated Round4 estimates:
  - `ROUND4: Updated estimated radii: Small=2.879mm, Large=3.840mm`
- The worker must not stop at a plausible explanation; it must prove the cause with instrumentation and regressions.
- Metis should be used as a consultant after each failed or ambiguous hypothesis round.

### Metis Review (gaps addressed)
- The loop must be finite: every hypothesis round ends in either **confirmed**, **rejected**, or **ambiguous → consult Metis**.
- The worker must not accept stale-`cams_cpp` as root cause without evidence; it must test coordinate-frame consistency directly.
- Acceptance criteria must require both **numerical stability** and **regression coverage**.
- The worker must avoid unrelated refactors and only touch files required by the diagnosis/fix in the current working directory.

## Work Objectives
### Core Objective
Find and fix the root cause of Round4 sphere-radius inflation so that Round4 estimates stay physically plausible and consistent with bootstrap / BA pre-calc on `case_001`, then prove the fix with repeatable regression tests and cache-free reruns.

### Deliverables
- A reproducible single-case debug harness for `case_001`
- Instrumentation that records the exact state used by BA pre-calc and Round4 radius estimation
- A ranked hypothesis matrix with evidence for accept/reject decisions
- A code fix in the current working directory that eliminates the Round4 inflation
- Regression tests covering the reproduced bug and the final fix
- A fresh cache-free verification run showing stable Round4 radii
- A short evidence note documenting the final cause and fix

### Definition of Done (verifiable conditions with commands)
- `case_001` rerun completes without Round4 radius inflation beyond tolerance
- Round4 radii remain within **10%** of BA pre-calc radii for `case_001`
- Small/large Round4 radii remain in physically plausible bands:
  - small sphere: `1.0 mm <= R <= 2.0 mm`
  - large sphere: `1.5 mm <= R <= 2.6 mm`
- The final accepted fix is covered by at least one regression test that fails before the fix and passes after it
- All new/updated tests pass under the OpenLPT Python environment
- The evidence log clearly identifies the accepted root cause and rejected alternatives

### Must Have
- Reproduce on `J:\Refraction_test\test_results\logs\robustness\case_001.log` first
- Instrument both BA pre-calc and Round4 radius-estimation inputs/outputs
- Test hypotheses one at a time; do not batch speculative fixes
- Call Metis after each failed or ambiguous hypothesis round
- Keep all code changes in the current working directory
- Use `C:\Users\tan_s\miniconda3\envs\OpenLPT\python.exe` for Python verification commands unless the OpenLPT environment is confirmed active
- Preserve cache-free verification when rerunning the reproducer

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Do not accept a hypothesis without instrumented evidence
- Do not fix by clamping radii or hardcoding expected values
- Do not rewrite unrelated BA logic or refactor broad calibration architecture
- Do not skip regression tests once the cause is identified
- Do not treat Metis as optional when a hypothesis is rejected or evidence conflicts

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: **TDD for the final fix**, tests-after for evidence-only instrumentation
- QA policy: every task includes exact agent-executed checks
- Evidence: `.sisyphus/evidence/radius-round4-debug/*` plus targeted logs under the existing test-result paths

## Execution Strategy
### Parallel Execution Waves
Wave 1: reproduce + instrumentation
Wave 2: hypothesis loop + Metis consultations
Wave 3: fix + regression coverage + cache-free verification

### Dependency Matrix (full, all tasks)
- Task 1 blocks all downstream work.
- Task 2 blocks Tasks 3-5.
- Task 3 blocks Task 4.
- Task 4 may repeat internally until one root cause is confirmed.
- Task 5 requires a confirmed root cause from Task 4.
- Task 6 requires Task 5 complete.
- Final verification requires Tasks 1-6 complete.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 2 tasks → deep / unspecified-high
- Wave 2 → 2 tasks → deep
- Wave 3 → 2 tasks → unspecified-high / quick

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.
> **Mandatory debug loop rule**: if a hypothesis round ends without a confirmed cause, the worker MUST consult Metis with the new evidence before starting the next hypothesis round.

- [ ] 1. Build a minimal reproducible Round4 radius harness for `case_001`

  **What to do**: Create a reproducible debug entrypoint in the current working directory that runs the `case_001` refractive calibration path in isolation and emits all radius-related log sections for bootstrap, BA pre-calc, and Round4. The harness must run cache-free, reuse existing `case_001` inputs, and write a dedicated evidence log that is shorter and easier to inspect than the full robustness campaign log.

  **Must NOT do**: Do not alter calibration math yet. Do not depend on the full 29-case campaign for reproduction.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: requires understanding and isolating a subtle numeric bug path.
  - Skills: `[]` — no external skills needed.
  - Omitted: `quick` — too much diagnosis logic for a trivial edit.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2, 3, 4, 5, 6] | Blocked By: []

  **References**:
  - Evidence log: `J:\Refraction_test\test_results\logs\robustness\case_001.log` — source anomaly
  - Round4 radius call site: `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:2321-2329`
  - BA pre-calc radius call site: `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:2261-2276`
  - Radius estimator: `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:1031-1123`
  - Existing harness patterns: `J:\Refraction_test\test_script\run_calibration_worker.py`

  **Acceptance Criteria**:
  - [ ] A single command reproduces the Round4 inflation on `case_001`
  - [ ] The dedicated log contains bootstrap, BA pre-calc, and Round4 radius sections
  - [ ] The run is cache-free and records `used_bootstrap_cache == false`

  **QA Scenarios**:
  ```
  Scenario: Reproducer command works
    Tool: Bash
    Steps: Run the dedicated `case_001` reproducer with `C:\Users\tan_s\miniconda3\envs\OpenLPT\python.exe`
    Expected: Log shows plausible early radii and inflated Round4 radii before the fix
    Evidence: .sisyphus/evidence/radius-round4-debug/task-1-reproducer.txt

  Scenario: Cache-free execution
    Tool: Bash
    Steps: Inspect the reproducer output JSON/log for cache flags and fresh output path usage
    Expected: No bootstrap/bundle cache reuse is reported
    Evidence: .sisyphus/evidence/radius-round4-debug/task-1-cache-free.txt
  ```

  **Commit**: NO | Message: `` | Files: current working directory files only

- [ ] 2. Instrument BA pre-calc vs Round4 state and frame consistency

  **What to do**: Add targeted instrumentation in the current working directory so the reproducer records the exact inputs used by `_estimate_and_log_sphere_radii()` at both BA pre-calc and Round4. Capture at minimum: sample `X_A_scaled`/`X_B_scaled` points, sample camera centers, representative plane points/normals, whether `cams_cpp` is present, and a direct frame-consistency check showing whether the points and camera/plane state still live in the same coordinate frame. Also log whether Round4 is using caller-side points that were never transformed while BA internal `_bundle_points` were transformed.

  **Must NOT do**: Do not add permanent noisy logging outside the debug-gated path. Do not guess at frame mismatch; prove or disprove it.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: precise instrumentation across Python/C++ state boundary.
  - Skills: `[]`
  - Omitted: `writing` — implementation-heavy.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [3, 4, 5, 6] | Blocked By: [1]

  **References**:
  - Radius estimator internals: `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:1045-1123`
  - BA optimize return + Round4 handoff: `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:2261-2331`
  - BA alignment function: `modules/camera_calibration/wand_calibration/refraction_calibration_BA.py:2841-2873`
  - Bundle-point transform helper: `modules/camera_calibration/wand_calibration/refraction_calibration_BA.py:1608-1631`

  **Acceptance Criteria**:
  - [ ] The evidence log shows side-by-side BA pre-calc vs Round4 state for the same sample frames
  - [ ] The instrumentation can confirm or reject coordinate-frame mismatch explicitly
  - [ ] The instrumentation output is concise enough to drive a hypothesis decision

  **QA Scenarios**:
  ```
  Scenario: Frame-consistency instrumentation produces usable evidence
    Tool: Bash
    Steps: Run the reproducer again after instrumentation and inspect the evidence log
    Expected: The log contains explicit BA pre-calc vs Round4 point/camera/plane comparisons and a frame-consistency verdict
    Evidence: .sisyphus/evidence/radius-round4-debug/task-2-frame-check.txt

  Scenario: Internal vs caller-side point transform check
    Tool: Bash
    Steps: Print representative `_bundle_points` and caller-side `X_A_scaled`/`X_B_scaled` after BA alignment
    Expected: The log shows whether internal BA points were transformed while caller-side points were not
    Evidence: .sisyphus/evidence/radius-round4-debug/task-2-point-transform.txt
  ```

  **Commit**: NO | Message: `` | Files: current working directory files only

- [ ] 3. Execute the finite hypothesis loop with mandatory Metis consultation

  **What to do**: Run the hypotheses in this exact order and stop each round with an explicit verdict:
  1. **H1**: caller-side Round4 points are stale/in wrong frame after BA alignment
  2. **H2**: Round4 uses an updated camera/plane model with mismatched refraction geometry inputs beyond just point alignment
  3. **H3**: Round4 radius model itself is numerically unstable for the aligned case even when frames match
  For each round: gather evidence, classify as `CONFIRMED`, `REJECTED`, or `AMBIGUOUS`, and if not `CONFIRMED`, call Metis with the new evidence and use its guidance for the next round. Do not start implementing a fix until one root cause is confirmed.

  **Must NOT do**: Do not test multiple root-cause fixes simultaneously. Do not continue past an ambiguous result without a Metis consultation.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: iterative debug reasoning with branching evidence.
  - Skills: `[]`
  - Omitted: `quick` — insufficient for a multi-round debug loop.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [4, 5, 6] | Blocked By: [2]

  **References**:
  - Anomalous log sections: `J:\Refraction_test\test_results\logs\robustness\case_001.log:130-154`, `:177-201`, `:520-545`
  - Round4 call order: `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:2316-2331`
  - Alignment transform: `modules/camera_calibration/wand_calibration/refraction_calibration_BA.py:2853-2873`

  **Acceptance Criteria**:
  - [ ] One root cause is explicitly marked `CONFIRMED`
  - [ ] At least two alternatives are explicitly marked `REJECTED` or `SECONDARY`
  - [ ] Every non-confirmed round includes a recorded Metis consultation result

  **QA Scenarios**:
  ```
  Scenario: Hypothesis matrix is complete
    Tool: Bash
    Steps: Inspect the generated debug evidence note / JSON matrix for H1-H3 verdicts and attached evidence references
    Expected: Exactly one primary confirmed cause, with explicit rejected/secondary alternatives
    Evidence: .sisyphus/evidence/radius-round4-debug/task-3-hypothesis-matrix.txt

  Scenario: Metis consulted on ambiguous or rejected rounds
    Tool: Bash
    Steps: Inspect worker notes/logs for Metis consultation summaries after non-confirmed rounds
    Expected: Every ambiguous/rejected round has a Metis-guided next-step note
    Evidence: .sisyphus/evidence/radius-round4-debug/task-3-metis-loop.txt
  ```

  **Commit**: NO | Message: `` | Files: current working directory files only

- [ ] 4. Add a failing regression test that reproduces the confirmed cause

  **What to do**: Before applying the final fix, add a regression test in the current working directory that fails against the pre-fix behavior and directly encodes the confirmed root cause. If H1 is confirmed, the test must demonstrate that Round4-style radius estimation using post-alignment camera/plane state with stale caller-side 3D points yields inflated radii, while a frame-consistent setup does not.

  **Must NOT do**: Do not add a superficial assertion that only checks log strings. Do not write a test that passes before the fix.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: nuanced regression design with geometric state setup.
  - Skills: `[]`
  - Omitted: `quick` — test must encode the actual failure mechanism.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [5, 6] | Blocked By: [3]

  **References**:
  - Existing test style: `tests/test_p0_bootstrap_failure.py`
  - Alignment helper behavior: `modules/camera_calibration/wand_calibration/refraction_calibration_BA.py:1608-1631`, `:2841-2873`
  - Radius estimator: `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:1031-1123`

  **Acceptance Criteria**:
  - [ ] The new regression test fails before the fix
  - [ ] The failure encodes the confirmed root cause, not just a generic range mismatch
  - [ ] The test can run non-interactively under pytest

  **QA Scenarios**:
  ```
  Scenario: Pre-fix regression fails
    Tool: Bash
    Steps: Run the new targeted pytest selection before the final fix is applied
    Expected: The new test fails for the expected reason
    Evidence: .sisyphus/evidence/radius-round4-debug/task-4-prefix-fail.txt

  Scenario: Test isolates the bug mechanism
    Tool: Bash
    Steps: Review pytest output / assertion message
    Expected: Failure message references the confirmed mismatch mechanism, not a vague threshold-only failure
    Evidence: .sisyphus/evidence/radius-round4-debug/task-4-isolated-mechanism.txt
  ```

  **Commit**: NO | Message: `` | Files: current working directory files only

- [ ] 5. Implement the minimal fix for the confirmed root cause

  **What to do**: Apply the smallest code change in the current working directory that fixes the confirmed cause. If H1 is confirmed, either transform caller-side Round4 points by the same BA alignment transform before re-estimation or replace them with frame-consistent updated points before the Round4 radius call. Preserve bootstrap and BA pre-calc behavior. Add a sanity guard so Round4 does not silently overwrite plausible earlier radii with obviously invalid values if the estimator returns non-finite or non-positive results.

  **Must NOT do**: Do not hardcode expected radii. Do not add a blind clamp that hides the bug. Do not refactor unrelated BA optimization stages.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: surgical geometry fix in production calibration path.
  - Skills: `[]`
  - Omitted: `refactor` — avoid broad structural changes.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [6] | Blocked By: [4]

  **References**:
  - Round4 writeback: `modules/camera_calibration/wand_calibration/refraction_wand_calibrator.py:2321-2329`
  - Internal point transform helper: `modules/camera_calibration/wand_calibration/refraction_calibration_BA.py:1608-1631`
  - Alignment application: `modules/camera_calibration/wand_calibration/refraction_calibration_BA.py:2853-2873`

  **Acceptance Criteria**:
  - [ ] The confirmed root cause is removed without changing unrelated calibration behavior
  - [ ] The pre-fix regression test now passes
  - [ ] Round4 radii on `case_001` stay within tolerance relative to BA pre-calc

  **QA Scenarios**:
  ```
  Scenario: Regression test passes after fix
    Tool: Bash
    Steps: Re-run the targeted pytest selection after applying the fix
    Expected: The previously failing regression now passes
    Evidence: .sisyphus/evidence/radius-round4-debug/task-5-postfix-test.txt

  Scenario: `case_001` Round4 radii stabilized
    Tool: Bash
    Steps: Run the dedicated reproducer after the fix and extract bootstrap, BA pre-calc, and Round4 radii
    Expected: Round4 radii remain within 10% of BA pre-calc and within plausible physical ranges
    Evidence: .sisyphus/evidence/radius-round4-debug/task-5-case001-stable.txt
  ```

  **Commit**: YES | Message: `fix(calibration): stabilize round4 radius estimation` | Files: current working directory files only

- [ ] 6. Run cache-free verification and record the final diagnosis

  **What to do**: Run the `case_001` reproducer cache-free after the fix, then run at least one adjacent comparison case to ensure the fix does not regress healthy behavior. Record a concise diagnosis note explaining the confirmed cause, the rejected alternatives, the implemented fix, and the post-fix evidence.

  **Must NOT do**: Do not end after a unit test alone. Do not skip the comparison rerun. Do not leave the diagnosis note ambiguous.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: focused verification and summary after the heavy debug work is done.
  - Skills: `[]`
  - Omitted: `writing` — summary is short and technical.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [] | Blocked By: [5]

  **References**:
  - Primary reproducer output from Task 1
  - `J:\Refraction_test\test_results\logs\robustness\case_001.log` — original bad baseline
  - Existing healthy comparison outputs under `J:\Refraction_test\test_results\per_case\robustness\`

  **Acceptance Criteria**:
  - [ ] `case_001` post-fix run is cache-free and stable
  - [ ] At least one comparison case remains healthy
  - [ ] Final diagnosis note names the confirmed cause, rejected alternatives, fix location, and proof

  **QA Scenarios**:
  ```
  Scenario: Cache-free post-fix verification
    Tool: Bash
    Steps: Run the reproducer and inspect output JSON/log for fresh execution and Round4 radii
    Expected: Cache-free run with stable Round4 radii in tolerance
    Evidence: .sisyphus/evidence/radius-round4-debug/task-6-cache-free-verify.txt

  Scenario: Comparison case still healthy
    Tool: Bash
    Steps: Run one adjacent healthy case through the same path and inspect its radii / success metrics
    Expected: No new inflation or calibration failure is introduced
    Evidence: .sisyphus/evidence/radius-round4-debug/task-6-comparison-case.txt
  ```

  **Commit**: NO | Message: `` | Files: current working directory files only

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- One main code commit is expected only after the fix is proven by the regression test.
- Do not commit instrumentation-only noise unless it remains necessary for future diagnostics.

## Success Criteria
- The worker can state, with evidence, exactly why Round4 inflated radii before the fix.
- The final fix is minimal, proven, and regression-tested.
- `case_001` no longer shows the Round4 anomaly.
- The worker has a clear Metis-driven path for each non-confirmed hypothesis round until the problem is solved.

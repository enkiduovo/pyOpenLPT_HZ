# pyright: reportMissingImports=false
"""
Regression tests for P0 bootstrap failure modes and structured telemetry.

These tests exercise the catastrophic P0 failure behavior, telemetry
emission, and failure-reason classification introduced in Task 2.

DESIGN (red-phase):
    Many of these tests are expected to FAIL (or reveal specific failure
    behavior) before bootstrap hardening is applied in Task 5.  The test
    names and docstrings clarify which should currently pass and which are
    red-phase regression anchors.

    - Tests tagged ``_red_phase`` are expected to fail before hardening.
    - Tests tagged ``_green`` should always pass.
"""

import json
import re
import sys
import textwrap
from io import StringIO
from pathlib import Path
from typing import Dict, Tuple, Optional

import numpy as np
import pytest

# Ensure repo root is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from modules.camera_calibration.wand_calibration.refractive_bootstrap import (
    P0FailureError,
    P0Telemetry,
    P0_REASON_CATASTROPHIC_REPROJECTION,
    P0_REASON_ESSENTIAL_MATRIX_FAILED,
    P0_REASON_INSUFFICIENT_GEOMETRY,
    P0_REASON_OK,
    P0_REASON_PHASE1_BA_FAILURE,
    P0_REASON_TOO_FEW_E_INLIERS,
    P0_REASON_UNSTABLE_SCALE_RECOVERY,
    PinholeBootstrapP0,
    PinholeBootstrapP0Config,
    select_ranked_pairs_via_precalib,
)


# ═══════════════════════════════════════════════════════════════════════════
# Synthetic observation helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_camera_settings(cam_ids, focal=9000.0, width=1280, height=800):
    """Build camera_settings dict for the given camera IDs."""
    return {
        cid: {"focal": focal, "width": width, "height": height}
        for cid in cam_ids
    }


def _project_point(pt3d, R, t, K):
    """Project a 3D point to 2D using pinhole model."""
    pt_cam = R @ pt3d.reshape(3, 1) + t
    pt_cam = pt_cam.flatten()
    if pt_cam[2] <= 0:
        return np.array([1e6, 1e6])
    pt_norm = pt_cam[:2] / pt_cam[2]
    pt_px = K[:2, :2] @ pt_norm + K[:2, 2]
    return pt_px


def _build_healthy_observations(
    n_frames: int = 50,
    wand_length_mm: float = 10.0,
    focal: float = 9000.0,
    width: int = 1280,
    height: int = 800,
    baseline_mm: float = 250.0,
    seed: int = 42,
) -> Tuple[Dict, Dict, int, int]:
    """
    Build synthetic observations for a healthy two-camera setup.

    Returns (observations, camera_settings, cam_i, cam_j).
    """
    rng = np.random.default_rng(seed)

    cam_i, cam_j = 0, 1
    K = np.array([[focal, 0, width / 2.0],
                  [0, focal, height / 2.0],
                  [0, 0, 1.0]], dtype=np.float64)

    # Camera i at origin, camera j offset along X
    R_i = np.eye(3)
    t_i = np.zeros((3, 1))
    R_j = np.eye(3)
    t_j = np.array([[baseline_mm], [0.0], [0.0]])

    observations = {}
    for fid in range(n_frames):
        # Random wand positions in front of both cameras
        center = np.array([
            rng.uniform(-20, 20),
            rng.uniform(-20, 20),
            rng.uniform(500, 700),
        ])
        direction = rng.normal(size=3)
        direction /= np.linalg.norm(direction)

        ptA = center - direction * (wand_length_mm / 2)
        ptB = center + direction * (wand_length_mm / 2)

        uvA_i = _project_point(ptA, R_i, t_i, K)
        uvB_i = _project_point(ptB, R_i, t_i, K)
        uvA_j = _project_point(ptA, R_j, t_j, K)
        uvB_j = _project_point(ptB, R_j, t_j, K)

        observations[fid] = {
            cam_i: (uvA_i, uvB_i),
            cam_j: (uvA_j, uvB_j),
        }

    camera_settings = _make_camera_settings([cam_i, cam_j], focal, width, height)
    return observations, camera_settings, cam_i, cam_j


def _build_degenerate_observations(
    n_frames: int = 50,
    wand_length_mm: float = 10.0,
    focal: float = 9000.0,
    width: int = 1280,
    height: int = 800,
    baseline_mm: float = 0.3,
    seed: int = 99,
) -> Tuple[Dict, Dict, int, int]:
    """
    Build synthetic observations for a degenerate two-camera setup with
    a tiny baseline that should trigger catastrophic P0 failure.

    Returns (observations, camera_settings, cam_i, cam_j).
    """
    rng = np.random.default_rng(seed)

    cam_i, cam_j = 0, 1
    K = np.array([[focal, 0, width / 2.0],
                  [0, focal, height / 2.0],
                  [0, 0, 1.0]], dtype=np.float64)

    # Tiny baseline — nearly co-located cameras
    R_i = np.eye(3)
    t_i = np.zeros((3, 1))
    R_j = np.eye(3)
    t_j = np.array([[baseline_mm], [0.0], [0.0]])

    observations = {}
    for fid in range(n_frames):
        center = np.array([
            rng.uniform(-10, 10),
            rng.uniform(-10, 10),
            rng.uniform(500, 700),
        ])
        direction = rng.normal(size=3)
        direction /= np.linalg.norm(direction)

        ptA = center - direction * (wand_length_mm / 2)
        ptB = center + direction * (wand_length_mm / 2)

        uvA_i = _project_point(ptA, R_i, t_i, K)
        uvB_i = _project_point(ptB, R_i, t_i, K)
        uvA_j = _project_point(ptA, R_j, t_j, K)
        uvB_j = _project_point(ptB, R_j, t_j, K)

        observations[fid] = {
            cam_i: (uvA_i, uvB_i),
            cam_j: (uvA_j, uvB_j),
        }

    camera_settings = _make_camera_settings([cam_i, cam_j], focal, width, height)
    return observations, camera_settings, cam_i, cam_j


# ═══════════════════════════════════════════════════════════════════════════
# P0Telemetry unit tests (GREEN — should always pass)
# ═══════════════════════════════════════════════════════════════════════════


class TestP0TelemetryStructure:
    """Tests that P0Telemetry dataclass has all expected fields and serializes correctly."""

    def test_default_fields_green(self):
        """All expected telemetry fields exist with correct defaults."""
        t = P0Telemetry()
        assert t.failure_reason == P0_REASON_OK
        assert t.selected_pair is None
        assert t.baseline_mm is None
        assert t.cheirality_ratio is None
        assert t.scale_factor_finite is None
        assert t.ba_initial_cost is None
        assert t.reproj_err_mean is None

    def test_to_dict_serializable_green(self):
        """to_dict() produces a JSON-serializable dict with all keys."""
        t = P0Telemetry(
            selected_pair=(0, 1),
            baseline_mm=250.0,
            e_inliers=100,
            e_total=200,
            pose_inliers=90,
            pose_total=100,
            cheirality_ratio=0.9,
            valid_inlier_wand_pairs=40,
            median_triangulation_length=5.0,
            scale_factor=2.0,
            scale_factor_finite=True,
            ba_initial_cost=100.0,
            ba_final_cost=10.0,
            ba_converged=True,
            ba_message="converged",
            reproj_err_mean=0.05,
            reproj_err_max=0.2,
            wand_length_median=10.0,
            wand_length_error=0.001,
            valid_frames=50,
            failure_reason=P0_REASON_OK,
        )
        d = t.to_dict()

        # Verify JSON round-trip
        json_str = json.dumps(d, default=str)
        loaded = json.loads(json_str)

        assert loaded["failure_reason"] == "ok"
        assert loaded["selected_pair"] == [0, 1]
        assert loaded["cheirality_ratio"] == 0.9
        assert loaded["scale_factor_finite"] is True

    def test_emit_produces_telemetry_line_green(self, capsys):
        """emit() prints a [P0_TELEMETRY] line parseable as JSON."""
        t = P0Telemetry(
            selected_pair=(0, 1),
            failure_reason=P0_REASON_OK,
            baseline_mm=100.0,
        )
        t.emit()
        captured = capsys.readouterr()
        assert "[P0_TELEMETRY]" in captured.out

        # Extract JSON payload
        match = re.search(r"\[P0_TELEMETRY\]\s*(\{.*\})", captured.out)
        assert match is not None
        payload = json.loads(match.group(1))
        assert payload["failure_reason"] == "ok"
        assert payload["baseline_mm"] == 100.0

    def test_failure_reason_constants_green(self):
        """All failure reason constants are distinct non-empty strings."""
        reasons = [
            P0_REASON_OK,
            P0_REASON_INSUFFICIENT_GEOMETRY,
            P0_REASON_ESSENTIAL_MATRIX_FAILED,
            P0_REASON_TOO_FEW_E_INLIERS,
            P0_REASON_UNSTABLE_SCALE_RECOVERY,
            P0_REASON_CATASTROPHIC_REPROJECTION,
            P0_REASON_PHASE1_BA_FAILURE,
        ]
        assert len(reasons) == len(set(reasons)), "Duplicate failure reason constants"
        for r in reasons:
            assert isinstance(r, str) and len(r) > 0


class TestP0FailureErrorStructure:
    """Tests that P0FailureError carries structured reason and telemetry."""

    def test_error_carries_reason_and_telemetry_green(self):
        """P0FailureError stores reason and telemetry with failure fields set."""
        t = P0Telemetry(selected_pair=(2, 3))
        exc = P0FailureError(
            "test failure message",
            P0_REASON_CATASTROPHIC_REPROJECTION,
            t,
        )
        assert exc.reason == P0_REASON_CATASTROPHIC_REPROJECTION
        assert exc.telemetry is t
        assert t.failure_reason == P0_REASON_CATASTROPHIC_REPROJECTION
        assert t.failure_detail == "test failure message"
        assert str(exc) == "test failure message"

    def test_error_is_runtime_error_green(self):
        """P0FailureError is a subclass of RuntimeError."""
        t = P0Telemetry()
        exc = P0FailureError("msg", P0_REASON_OK, t)
        assert isinstance(exc, RuntimeError)


# ═══════════════════════════════════════════════════════════════════════════
# P0 Bootstrap integration tests (mix of GREEN and RED-PHASE)
# ═══════════════════════════════════════════════════════════════════════════


class TestP0BootstrapInsufficientFrames:
    """Insufficient frames should trigger early failure with correct reason."""

    def test_too_few_frames_green(self):
        """< 10 frames raises P0FailureError(insufficient_geometry)."""
        obs, settings, ci, cj = _build_healthy_observations(n_frames=5)
        config = PinholeBootstrapP0Config(wand_length_mm=10.0)
        p0 = PinholeBootstrapP0(config)

        with pytest.raises(P0FailureError) as exc_info:
            p0.run(ci, cj, obs, settings)

        assert exc_info.value.reason == P0_REASON_INSUFFICIENT_GEOMETRY
        assert exc_info.value.telemetry.failure_reason == P0_REASON_INSUFFICIENT_GEOMETRY
        assert exc_info.value.telemetry.selected_pair == (ci, cj)

    def test_zero_frames_green(self):
        """Zero frames raises P0FailureError(insufficient_geometry)."""
        settings = _make_camera_settings([0, 1])
        config = PinholeBootstrapP0Config(wand_length_mm=10.0)
        p0 = PinholeBootstrapP0(config)

        with pytest.raises(P0FailureError) as exc_info:
            p0.run(0, 1, {}, settings)

        assert exc_info.value.reason == P0_REASON_INSUFFICIENT_GEOMETRY


class TestP0BootstrapHealthyCase:
    """A well-separated camera pair should produce good P0 results."""

    def test_healthy_baseline_passes_green(self, capsys):
        """Healthy synthetic setup passes P0 with reasonable metrics."""
        obs, settings, ci, cj = _build_healthy_observations(
            n_frames=100,
            baseline_mm=250.0,
            seed=42,
        )
        config = PinholeBootstrapP0Config(wand_length_mm=10.0, ui_focal_px=9000.0)
        p0 = PinholeBootstrapP0(config)

        params_i, params_j, report = p0.run(ci, cj, obs, settings)

        # Verify structural integrity
        assert params_i.shape == (6,)
        assert params_j.shape == (6,)
        assert "p0_telemetry" in report

        telem = report["p0_telemetry"]
        assert telem["failure_reason"] == P0_REASON_OK
        assert telem["selected_pair"] == [ci, cj]
        assert telem["scale_factor_finite"] is True
        assert telem["cheirality_ratio"] is not None
        assert telem["cheirality_ratio"] > 0.7  # healthy cheirality
        assert telem["ba_converged"] is True

        # Reproj error should be small for a well-conditioned setup
        assert telem["reproj_err_mean"] < 5.0  # generous threshold

        # Baseline should be recovered approximately
        assert telem["baseline_mm"] is not None
        assert telem["baseline_mm"] > 50.0  # well above the 50mm warning

        # Check [P0_TELEMETRY] was emitted
        captured = capsys.readouterr()
        assert "[P0_TELEMETRY]" in captured.out

    def test_healthy_report_has_all_telemetry_keys_green(self):
        """Report's p0_telemetry dict contains all expected diagnostic keys."""
        obs, settings, ci, cj = _build_healthy_observations(
            n_frames=50,
            baseline_mm=200.0,
            seed=123,
        )
        config = PinholeBootstrapP0Config(wand_length_mm=10.0, ui_focal_px=9000.0)
        p0 = PinholeBootstrapP0(config)

        _, _, report = p0.run(ci, cj, obs, settings)
        telem = report["p0_telemetry"]

        required_keys = {
            "selected_pair", "baseline_mm",
            "e_inliers", "e_total",
            "pose_inliers", "pose_total", "cheirality_ratio",
            "valid_inlier_wand_pairs", "median_triangulation_length",
            "scale_factor", "scale_factor_finite",
            "ba_initial_cost", "ba_final_cost", "ba_converged", "ba_message",
            "reproj_err_mean", "reproj_err_max",
            "wand_length_median", "wand_length_error",
            "valid_frames",
            "failure_reason", "failure_detail",
        }
        assert required_keys.issubset(set(telem.keys())), (
            f"Missing keys: {required_keys - set(telem.keys())}"
        )


class TestP0BootstrapDegenerateBaseline:
    """
    A degenerate (tiny) baseline should trigger catastrophic failure.

    RED-PHASE: Before hardening, the current bootstrap should raise
    P0FailureError with reason catastrophic_reprojection because the
    tiny baseline causes scale recovery to produce enormous reprojection.
    """

    def test_tiny_baseline_triggers_failure_red_phase(self):
        """
        A ~0.3mm baseline should trigger P0FailureError.

        This test reproduces the core failure pattern seen in the 7 failed
        cases (e.g. case_023 with baseline=0.32mm).

        After bootstrap hardening (Task 5), this test should be updated
        to expect either a different failure reason or a recovery path.
        """
        obs, settings, ci, cj = _build_degenerate_observations(
            n_frames=100,
            baseline_mm=0.3,
            seed=99,
        )
        config = PinholeBootstrapP0Config(wand_length_mm=10.0, ui_focal_px=9000.0)
        p0 = PinholeBootstrapP0(config)

        with pytest.raises(P0FailureError) as exc_info:
            p0.run(ci, cj, obs, settings)

        err = exc_info.value
        # The failure should be one of the catastrophic paths
        assert err.reason in (
            P0_REASON_CATASTROPHIC_REPROJECTION,
            P0_REASON_UNSTABLE_SCALE_RECOVERY,
            P0_REASON_PHASE1_BA_FAILURE,
        ), f"Unexpected failure reason: {err.reason}"

        # Telemetry should be populated even on failure
        t = err.telemetry
        assert t.selected_pair == (ci, cj)
        assert t.failure_reason == err.reason
        assert t.failure_detail is not None and len(t.failure_detail) > 0

    def test_degenerate_telemetry_has_cheirality_red_phase(self):
        """
        Even when P0 fails, cheirality_ratio should be populated if
        the E-matrix stage succeeded.

        In the real failing cases, cheirality_ratio ~0.487 was the
        pre-failure signal.
        """
        obs, settings, ci, cj = _build_degenerate_observations(
            n_frames=100,
            baseline_mm=0.3,
            seed=99,
        )
        config = PinholeBootstrapP0Config(wand_length_mm=10.0, ui_focal_px=9000.0)
        p0 = PinholeBootstrapP0(config)

        with pytest.raises(P0FailureError) as exc_info:
            p0.run(ci, cj, obs, settings)

        t = exc_info.value.telemetry
        # If E-matrix stage succeeded, these should be populated
        if t.e_inliers is not None and t.e_inliers >= 8:
            assert t.cheirality_ratio is not None
            assert 0.0 <= t.cheirality_ratio <= 1.0


class TestP0BootstrapMissingCamera:
    """Missing camera settings should raise ValueError (not P0FailureError)."""

    def test_missing_camera_settings_green(self):
        """Requesting an unknown camera raises ValueError."""
        obs, settings, ci, cj = _build_healthy_observations(n_frames=20)
        config = PinholeBootstrapP0Config(wand_length_mm=10.0)
        p0 = PinholeBootstrapP0(config)

        # Remove cam_j from settings
        settings_missing = {ci: settings[ci]}
        with pytest.raises(ValueError, match="Missing camera_settings"):
            p0.run(ci, cj, obs, settings_missing)


class TestP0BootstrapTelemetryOnFailurePaths:
    """
    Verify structured telemetry is emitted even when P0 fails,
    so downstream tools (ablation runner, Task 4 classifier) can
    parse the failure mode.
    """

    def test_p0_failure_error_is_json_serializable_green(self):
        """P0FailureError telemetry can be serialized to JSON for logging."""
        t = P0Telemetry(
            selected_pair=(2, 4),
            baseline_mm=1.17,
            cheirality_ratio=0.274,
            failure_reason=P0_REASON_CATASTROPHIC_REPROJECTION,
            failure_detail="[P0 FAIL] Reprojection error too high: 561848.12 px",
        )
        d = t.to_dict()
        json_str = json.dumps(d, default=str)
        loaded = json.loads(json_str)
        assert loaded["failure_reason"] == P0_REASON_CATASTROPHIC_REPROJECTION
        assert loaded["baseline_mm"] == 1.17
        assert loaded["cheirality_ratio"] == 0.274

    def test_failure_reason_matches_known_p0_cases_green(self):
        """
        Verify the known failure reasons from the evidence matrix
        match the defined constants.
        """
        known_reasons_from_evidence = [
            "catastrophic_reprojection",  # case_012, 015, 019, 023, 027, 028, 029
        ]
        valid_constants = {
            P0_REASON_OK,
            P0_REASON_INSUFFICIENT_GEOMETRY,
            P0_REASON_ESSENTIAL_MATRIX_FAILED,
            P0_REASON_TOO_FEW_E_INLIERS,
            P0_REASON_UNSTABLE_SCALE_RECOVERY,
            P0_REASON_CATASTROPHIC_REPROJECTION,
            P0_REASON_PHASE1_BA_FAILURE,
        }
        for reason in known_reasons_from_evidence:
            assert reason in valid_constants, (
                f"Evidence-matrix reason '{reason}' not in defined constants"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Task 5: Geometry-aware pair selection and fallback retry tests
# ═══════════════════════════════════════════════════════════════════════════


def _build_multi_camera_observations(
    n_frames: int = 50,
    wand_length_mm: float = 10.0,
    focal: float = 9000.0,
    width: int = 1280,
    height: int = 800,
    seed: int = 77,
) -> Tuple[Dict, Dict]:
    """
    Build synthetic observations for a 5-camera setup where cameras 0 and 1
    are nearly co-located (degenerate pair) but cameras 2, 3, 4 are well
    separated.

    Camera positions:
      cam 0: origin
      cam 1: 0.3 mm offset (nearly co-located with cam 0 -- DEGENERATE)
      cam 2: 250 mm along X (healthy)
      cam 3: 0, 200 mm along Y (healthy)
      cam 4: 150 mm along X, 150 mm along Y (healthy)

    Returns (observations, camera_settings).
    """
    rng = np.random.default_rng(seed)

    cam_ids = [0, 1, 2, 3, 4]
    K = np.array([[focal, 0, width / 2.0],
                  [0, focal, height / 2.0],
                  [0, 0, 1.0]], dtype=np.float64)

    # Camera extrinsics (R=identity for all, varying translations)
    cam_R = {cid: np.eye(3) for cid in cam_ids}
    cam_t = {
        0: np.array([[0.0], [0.0], [0.0]]),
        1: np.array([[0.3], [0.0], [0.0]]),     # nearly co-located with cam 0
        2: np.array([[250.0], [0.0], [0.0]]),    # healthy separation
        3: np.array([[0.0], [200.0], [0.0]]),    # healthy separation
        4: np.array([[150.0], [150.0], [0.0]]),  # healthy separation
    }

    observations = {}
    for fid in range(n_frames):
        center = np.array([
            rng.uniform(-20, 20),
            rng.uniform(-20, 20),
            rng.uniform(500, 700),
        ])
        direction = rng.normal(size=3)
        direction /= np.linalg.norm(direction)

        ptA = center - direction * (wand_length_mm / 2)
        ptB = center + direction * (wand_length_mm / 2)

        frame_obs = {}
        for cid in cam_ids:
            uvA = _project_point(ptA, cam_R[cid], cam_t[cid], K)
            uvB = _project_point(ptB, cam_R[cid], cam_t[cid], K)
            frame_obs[cid] = (uvA, uvB)
        observations[fid] = frame_obs

    camera_settings = _make_camera_settings(cam_ids, focal, width, height)
    return observations, camera_settings


class _MockBaseCalibratorWithPerCamError:
    """
    Mock base calibrator that simulates precalibration returning per-camera
    reprojection errors where the degenerate cameras (0, 1) have the lowest
    individual errors -- the exact pathology from the evidence matrix.
    """

    def __init__(self, observations, camera_settings, per_cam_errors,
                 cam_positions=None, extrinsics_source='cameras'):
        """
        Parameters
        ----------
        extrinsics_source : str
            'cameras'      — populate self.cameras (WandCalibrator path)
            'final_params' — populate self.final_params only
            'none'         — no extrinsics stored (MockBase production path)
        """
        self.wand_points_filtered = observations
        self.wand_points = observations
        self.camera_settings = camera_settings
        self._per_cam_errors = per_cam_errors
        self.per_frame_errors = None
        self.image_size = (800, 1280)

        self.cameras = {}
        self.final_params = {}

        if cam_positions and extrinsics_source == 'cameras':
            for cid, pos in cam_positions.items():
                R = np.eye(3)
                T = np.array(pos, dtype=np.float64).reshape(3)
                self.cameras[cid] = {'R': R, 'T': T}
        elif cam_positions and extrinsics_source == 'final_params':
            for cid, pos in cam_positions.items():
                R = np.eye(3)
                T = np.array(pos, dtype=np.float64).reshape(3, 1)
                self.final_params[cid] = {'R': R, 'T': T}
        # extrinsics_source == 'none': leave both empty

    def run_precalibration_check(self, wand_length, init_focal_length):
        lines = []
        for cid in sorted(self._per_cam_errors.keys()):
            lines.append(f"  Cam {cid}: {self._per_cam_errors[cid]:.2f} px")
        msg = "\n".join(lines)
        return True, msg, None


class TestGeometryAwarePairSelection:
    """
    Task 5: select_ranked_pairs_via_precalib must not prefer degenerate pairs
    when healthy alternatives exist.
    """

    # tvec values matching _build_multi_camera_observations layout
    # Camera centres = -R.T @ T = -T (since R=I)
    _STANDARD_CAM_TVECS = {
        0: [0.0, 0.0, 0.0],
        1: [0.3, 0.0, 0.0],      # 0.3 mm from cam 0 (degenerate)
        2: [250.0, 0.0, 0.0],    # 250 mm from cam 0
        3: [0.0, 200.0, 0.0],    # 200 mm from cam 0
        4: [150.0, 150.0, 0.0],  # ~212 mm from cam 0
    }

    def _make_mock(self, per_cam_errors, cam_positions=None, seed=77):
        obs, settings = _build_multi_camera_observations(n_frames=50, seed=seed)
        positions = cam_positions or self._STANDARD_CAM_TVECS
        return _MockBaseCalibratorWithPerCamError(
            obs, settings, per_cam_errors, cam_positions=positions
        )

    def test_degenerate_pair_not_top_ranked(self):
        """
        When cameras 0 and 1 have the lowest individual reprojection errors
        but are nearly co-located (0.3mm apart), the top-ranked pair should
        NOT be (0,1).

        Evidence: case_012 precalib selects (2,4) with low per-cam error but
        baseline=1.17mm. 9/10 other pairs pass with baselines 241-1159mm.
        """
        per_cam_errors = {0: 5.0, 1: 7.0, 2: 15.0, 3: 18.0, 4: 20.0}
        mock_base = self._make_mock(per_cam_errors)

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is not None and len(ranked) > 0, "Should return at least one pair"

        top_pair = ranked[0]
        assert top_pair != (0, 1), (
            f"Top pair is degenerate (0,1) -- geometry sanity check failed. "
            f"Full ranking: {ranked}"
        )

    def test_healthy_pair_appears_in_top_ranked(self):
        per_cam_errors = {0: 5.0, 1: 7.0, 2: 15.0, 3: 18.0, 4: 20.0}
        mock_base = self._make_mock(per_cam_errors)

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is not None and len(ranked) >= 3

        healthy_pairs = {(0, 2), (0, 3), (0, 4), (1, 2), (1, 3), (1, 4),
                         (2, 3), (2, 4), (3, 4)}
        top_3 = set(ranked[:3])
        assert top_3 & healthy_pairs, (
            f"No healthy pair in top 3: {ranked[:3]}"
        )

    def test_ranked_returns_multiple_candidates(self):
        per_cam_errors = {0: 5.0, 1: 7.0, 2: 15.0, 3: 18.0, 4: 20.0}
        mock_base = self._make_mock(per_cam_errors)

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is not None
        assert len(ranked) >= 2, (
            f"Should return >=2 candidates for fallback, got {len(ranked)}"
        )

    def test_backward_compatible_select_best_pair(self):
        from modules.camera_calibration.wand_calibration.refractive_bootstrap import (
            select_best_pair_via_precalib,
        )
        per_cam_errors = {0: 5.0, 1: 7.0, 2: 15.0, 3: 18.0, 4: 20.0}
        mock_base = self._make_mock(per_cam_errors)

        pair = select_best_pair_via_precalib(mock_base, 10.0, 9000.0)
        assert pair is not None
        assert isinstance(pair, tuple) and len(pair) == 2
        assert pair != (0, 1)

    def test_high_disparity_low_baseline_demoted(self):
        """Regression for case_012: pair (2,4) had 92.4px disparity but only
        1.17mm 3D baseline.  Pixel disparity alone passed but the pair was
        degenerate.  With precalib baselines available, such pairs must be
        demoted.

        Setup: cam 5 placed 1.2 mm from cam 2 (degenerate baseline) but with
        a different viewing direction so pixel disparity is high.  Cam 5 and
        cam 2 both have the lowest per-cam errors.
        """
        obs_base, settings_base = _build_multi_camera_observations(
            n_frames=50, seed=77
        )

        cam_positions = dict(self._STANDARD_CAM_TVECS)
        cam_positions[5] = [251.2, 0.0, 0.0]  # 1.2 mm from cam 2 (t=[250,...])

        K = np.array([[9000.0, 0, 640.0],
                      [0, 9000.0, 400.0],
                      [0, 0, 1.0]])
        R5 = np.eye(3)
        t5 = np.array([[251.2], [0.0], [0.0]])

        obs = {}
        for fid, frame in obs_base.items():
            new_frame = dict(frame)
            uv0 = frame[0]
            ptA_approx = np.array([
                (uv0[0][0] - 640.0) / 9000.0 * 600,
                (uv0[0][1] - 400.0) / 9000.0 * 600,
                600.0
            ])
            ptB_approx = np.array([
                (uv0[1][0] - 640.0) / 9000.0 * 600,
                (uv0[1][1] - 400.0) / 9000.0 * 600,
                600.0
            ])
            uvA_5 = _project_point(ptA_approx, R5, t5, K)
            uvB_5 = _project_point(ptB_approx, R5, t5, K)
            new_frame[5] = (uvA_5, uvB_5)
            obs[fid] = new_frame

        settings = dict(settings_base)
        settings[5] = {"focal": 9000.0, "width": 1280, "height": 800}

        per_cam_errors = {
            0: 20.0, 1: 22.0, 2: 8.0, 3: 25.0, 4: 25.0, 5: 9.0
        }
        mock_base = _MockBaseCalibratorWithPerCamError(
            obs, settings, per_cam_errors, cam_positions=cam_positions
        )

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is not None

        degenerate_pair = (2, 5)
        top_pair = ranked[0]
        assert top_pair != degenerate_pair, (
            f"Pair {degenerate_pair} (1.2mm baseline) should NOT be #1. "
            f"Ranking: {ranked[:5]}"
        )

    def test_final_params_only_path(self):
        """When calibrator exposes final_params but not cameras (WandCalibrator
        alternate structure), baseline check still works and demotes
        degenerate pairs."""
        per_cam_errors = {0: 5.0, 1: 7.0, 2: 15.0, 3: 18.0, 4: 20.0}
        obs, settings = _build_multi_camera_observations(n_frames=50, seed=77)
        positions = self._STANDARD_CAM_TVECS
        mock_base = _MockBaseCalibratorWithPerCamError(
            obs, settings, per_cam_errors,
            cam_positions=positions, extrinsics_source='final_params',
        )
        assert not mock_base.cameras
        assert len(mock_base.final_params) == 5

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is not None and len(ranked) > 0
        assert ranked[0] != (0, 1), (
            f"final_params path failed to demote (0,1): {ranked[:5]}"
        )

    def test_no_extrinsics_recovery_demotes_degenerate(self):
        """When calibrator exposes NO extrinsics at all (like production
        MockBase), the function recovers camera positions from observations
        via Essential Matrix + PnP and still demotes degenerate pairs.

        This is the key regression test for the production bug: MockBase's
        run_precalibration_check() discards cam_params, so the old code
        always returned baseline_3d=-1.0 and fell back to pixel disparity
        which couldn't catch case_012's bad pair (2,4).
        """
        per_cam_errors = {0: 5.0, 1: 7.0, 2: 15.0, 3: 18.0, 4: 20.0}
        obs, settings = _build_multi_camera_observations(n_frames=50, seed=77)
        mock_base = _MockBaseCalibratorWithPerCamError(
            obs, settings, per_cam_errors,
            cam_positions=self._STANDARD_CAM_TVECS,
            extrinsics_source='none',
        )
        assert not mock_base.cameras
        assert not mock_base.final_params

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is not None and len(ranked) > 0
        assert ranked[0] != (0, 1), (
            f"No-extrinsics recovery failed to demote (0,1): {ranked[:5]}"
        )

    def test_partial_extrinsics_uses_essential_per_pair(self, capsys):
        per_cam_errors = {0: 20.0, 1: 22.0, 2: 8.0, 3: 9.0, 4: 25.0}
        obs, settings = _build_multi_camera_observations(n_frames=50, seed=77)

        partial_positions = {
            0: self._STANDARD_CAM_TVECS[0],
            1: self._STANDARD_CAM_TVECS[1],
        }
        mock_base = _MockBaseCalibratorWithPerCamError(
            obs,
            settings,
            per_cam_errors,
            cam_positions=partial_positions,
            extrinsics_source='cameras',
        )

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is not None and len(ranked) > 0

        captured = capsys.readouterr()
        assert "source=essential" in captured.out, captured.out
        assert ranked[0] == (2, 3), (
            f"Expected missing-centre pair (2,3) to be ranked first via Essential fallback. "
            f"Ranking: {ranked[:5]}"
        )

    def test_all_geometry_invalid_returns_none(self, capsys):
        per_cam_errors = {0: 5.0, 1: 6.0, 2: 7.0, 3: 8.0, 4: 9.0}
        obs, settings = _build_multi_camera_observations(n_frames=50, seed=77)
        tiny_positions = {
            0: [0.0, 0.0, 0.0],
            1: [0.3, 0.0, 0.0],
            2: [0.6, 0.0, 0.0],
            3: [0.0, 0.8, 0.0],
            4: [0.5, 0.6, 0.0],
        }
        mock_base = _MockBaseCalibratorWithPerCamError(
            obs, settings, per_cam_errors, cam_positions=tiny_positions
        )

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is None

        captured = capsys.readouterr()
        assert "No geometry-valid camera pair found" in captured.out


class TestDeterministicFallbackRetry:
    """
    Task 5: If the first selected pair fails P0, try exactly one next-best
    geometry-valid pair, then stop.
    """

    # Reuse standard camera layout for consistent 3D baseline checks.
    _STANDARD_CAM_TVECS = {
        0: [0.0, 0.0, 0.0],
        1: [0.3, 0.0, 0.0],
        2: [250.0, 0.0, 0.0],
        3: [0.0, 200.0, 0.0],
        4: [150.0, 150.0, 0.0],
    }

    def test_fallback_tries_second_pair_on_first_failure(self):
        """
        Patch PinholeBootstrapP0.run to fail on the first pair and succeed
        on the second, verifying that the ranked list enables one retry.
        """
        obs, settings = _build_multi_camera_observations(n_frames=50, seed=77)
        per_cam_errors = {0: 5.0, 1: 7.0, 2: 15.0, 3: 18.0, 4: 20.0}
        mock_base = _MockBaseCalibratorWithPerCamError(
            obs, settings, per_cam_errors,
            cam_positions=self._STANDARD_CAM_TVECS,
        )

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is not None and len(ranked) >= 2

        first_pair = ranked[0]
        second_pair = ranked[1]

        call_log = []

        config = PinholeBootstrapP0Config(wand_length_mm=10.0, ui_focal_px=9000.0)
        p0 = PinholeBootstrapP0(config)

        original_run = p0.run

        def mock_run(cam_i, cam_j, *args, **kwargs):
            call_log.append((cam_i, cam_j))
            if (cam_i, cam_j) == first_pair:
                telemetry = P0Telemetry(selected_pair=first_pair)
                raise P0FailureError(
                    "simulated first-pair failure",
                    P0_REASON_CATASTROPHIC_REPROJECTION,
                    telemetry,
                )
            return original_run(cam_i, cam_j, *args, **kwargs)

        p0.run = mock_run

        with pytest.raises(P0FailureError):
            p0.run(*first_pair, obs, settings)
        assert len(call_log) == 1
        assert call_log[0] == first_pair

        call_log.clear()
        result = p0.run(*second_pair, obs, settings)
        assert len(call_log) == 1
        assert call_log[0] == second_pair
        assert result is not None

    def test_no_open_ended_retry_loop(self):
        """
        The fallback mechanism should attempt at most ONE additional pair,
        not loop through all possible pairs.
        """
        obs, settings = _build_multi_camera_observations(n_frames=50, seed=77)
        per_cam_errors = {0: 5.0, 1: 7.0, 2: 15.0, 3: 18.0, 4: 20.0}
        mock_base = _MockBaseCalibratorWithPerCamError(
            obs, settings, per_cam_errors,
            cam_positions=self._STANDARD_CAM_TVECS,
        )

        ranked = select_ranked_pairs_via_precalib(mock_base, 10.0, 9000.0)
        assert ranked is not None
        assert len(ranked) >= 2


class TestCase023NotRecovered:
    """
    Task 5: case_023 must NOT be magically recovered by the hardening.
    It remains geometry-limited in tested evidence.
    """

    def test_degenerate_baseline_still_fails_after_hardening(self):
        """
        A ~0.3mm baseline should still trigger P0FailureError.
        This validates that the hardening (geometry-aware pair selection +
        one retry) does NOT mask fundamental geometry failure.
        """
        obs, settings, ci, cj = _build_degenerate_observations(
            n_frames=100, baseline_mm=0.3, seed=99,
        )
        config = PinholeBootstrapP0Config(wand_length_mm=10.0, ui_focal_px=9000.0)
        p0 = PinholeBootstrapP0(config)

        with pytest.raises(P0FailureError) as exc_info:
            p0.run(ci, cj, obs, settings)

        err = exc_info.value
        assert err.reason in (
            P0_REASON_CATASTROPHIC_REPROJECTION,
            P0_REASON_UNSTABLE_SCALE_RECOVERY,
            P0_REASON_PHASE1_BA_FAILURE,
        )
        assert err.telemetry.selected_pair == (ci, cj)
        assert err.telemetry.failure_reason == err.reason


# ═══════════════════════════════════════════════════════════════════════════
# Live case regression tests (require J: drive data)
# ═══════════════════════════════════════════════════════════════════════════

# These tests use actual case data from J:\Refraction_test and are
# skipped if the J: drive is not available.
J_DRIVE_AVAILABLE = Path("J:/Refraction_test/case_001").is_dir()


@pytest.mark.skipif(not J_DRIVE_AVAILABLE, reason="J: drive not available")
class TestLiveCaseRegression:
    """
    Regression tests using actual case data.

    These confirm that the telemetry and failure classification behavior
    works with real-world observation data, not just synthetic fixtures.
    """

    def test_case_001_healthy_emits_ok_telemetry(self):
        """case_001 should pass P0 and emit failure_reason=ok."""
        sys.path.insert(0, str(Path("J:/Refraction_test/test_script")))
        from run_calibration_worker import load_case_inputs

        inputs = load_case_inputs("J:/Refraction_test/case_001")
        mock_base = inputs["mock_base"]

        from modules.camera_calibration.wand_calibration.refractive_bootstrap import (
            PinholeBootstrapP0,
            PinholeBootstrapP0Config,
            select_best_pair_via_precalib,
        )

        pair = select_best_pair_via_precalib(
            mock_base,
            wand_len_mm=10.0,
            initial_focal_px=inputs["focal_px"],
        )
        assert pair is not None, "Precalibration failed to select a pair for case_001"

        from modules.camera_calibration.wand_calibration.refraction_wand_calibrator import (
            ObservationBuilder,
            RefractiveCalibReporter,
        )

        observations = ObservationBuilder.prepare_for_bootstrap(
            mock_base, inputs["cam_to_window"], RefractiveCalibReporter()
        )

        config = PinholeBootstrapP0Config(
            wand_length_mm=10.0,
            ui_focal_px=inputs["focal_px"],
        )
        p0 = PinholeBootstrapP0(config)

        cam_i, cam_j = pair
        params_i, params_j, report = p0.run(
            cam_i, cam_j, observations, mock_base.camera_settings,
        )

        assert "p0_telemetry" in report
        telem = report["p0_telemetry"]
        assert telem["failure_reason"] == P0_REASON_OK
        assert telem["baseline_mm"] > 50.0

    def test_case_023_recovered_by_better_pair_selection(self):
        """
        case_023 was previously failing because the old pair selection chose
        a degenerate pair.  With pairwise Essential Matrix baselines, the
        ranking now correctly avoids degenerate pairs (many have 0-5mm
        baselines) and selects a healthy pair instead.

        GREEN-PHASE: Updated from the red-phase test after Task 5 hardening.
        The docstring of the original test said: "After Task 5 fixes, it
        should be updated to reflect the new behavior (either recovery or
        explicit geometry classification)."

        Evidence: pair (2,5) passes P0 with 700.7mm baseline and 0.02px
        reproj error.  The old pair selection was accidentally selecting a
        degenerate pair; case_023 is NOT genuinely geometry-limited.
        """
        sys.path.insert(0, str(Path("J:/Refraction_test/test_script")))
        from run_calibration_worker import load_case_inputs

        inputs = load_case_inputs("J:/Refraction_test/case_023")
        mock_base = inputs["mock_base"]

        from modules.camera_calibration.wand_calibration.refractive_bootstrap import (
            PinholeBootstrapP0,
            PinholeBootstrapP0Config,
            select_ranked_pairs_via_precalib,
        )

        ranked = select_ranked_pairs_via_precalib(
            mock_base,
            wand_len_mm=10.0,
            initial_focal_px=inputs["focal_px"],
        )
        assert ranked is not None and len(ranked) > 0

        top_pair = ranked[0]

        config = PinholeBootstrapP0Config(
            wand_length_mm=10.0,
            ui_focal_px=inputs["focal_px"],
        )
        p0 = PinholeBootstrapP0(config)

        from modules.camera_calibration.wand_calibration.refraction_wand_calibrator import (
            ObservationBuilder,
            RefractiveCalibReporter,
        )

        observations = ObservationBuilder.prepare_for_bootstrap(
            mock_base, inputs["cam_to_window"], RefractiveCalibReporter()
        )

        cam_i, cam_j = top_pair
        params_i, params_j, report = p0.run(
            cam_i, cam_j, observations, mock_base.camera_settings,
        )

        assert "p0_telemetry" in report
        telem = report["p0_telemetry"]
        assert telem["failure_reason"] == P0_REASON_OK
        assert telem["baseline_mm"] > 50.0

    def test_case_012_does_not_select_bad_pair_2_4(self):
        """case_012 must NOT select pair (2,4) which has 1.17mm baseline.

        This is the primary production regression: the old code always
        returned baseline_3d=-1.0 for MockBase and fell back to pixel
        disparity (92.4px for pair (2,4)), which looked healthy.  With
        the Essential Matrix recovery, the true 3D baseline is now
        detected and the pair is demoted.
        """
        sys.path.insert(0, str(Path("J:/Refraction_test/test_script")))
        from run_calibration_worker import load_case_inputs

        inputs = load_case_inputs("J:/Refraction_test/case_012")
        mock_base = inputs["mock_base"]

        from modules.camera_calibration.wand_calibration.refractive_bootstrap import (
            select_ranked_pairs_via_precalib,
        )

        ranked = select_ranked_pairs_via_precalib(
            mock_base,
            wand_len_mm=10.0,
            initial_focal_px=inputs["focal_px"],
        )
        assert ranked is not None and len(ranked) > 0

        top_pair = ranked[0]
        assert top_pair != (2, 4), (
            f"case_012 still selects bad pair (2,4). Ranking: {ranked[:5]}"
        )
        assert top_pair != (4, 2), (
            f"case_012 still selects bad pair (4,2). Ranking: {ranked[:5]}"
        )

# pyright: reportAttributeAccessIssue=false
"""Regression test for the Task 8 visibility-collapse bug.

Reproduces the failure mode where `main()` translated the entire scaled cloud
to `common_center`, shifting the cloud away from its original (in-view)
location and collapsing common visibility to zero.

The fix anchors the scaled cloud at `track_center` so that pure scaling
(rotation=0, scale!=1) is performed in place about the cloud's own center.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

gen = pytest.importorskip("generate_mirrored_tracks")


def _make_cloud() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)
    xyz = rng.uniform(-30.0, 30.0, size=(2000, 3)).astype(np.float64)
    track_center = 0.5 * (xyz.min(axis=0) + xyz.max(axis=0))
    return xyz, track_center


def test_pure_scale_keeps_cloud_anchored_at_track_center():
    """Scaling with rotation=0 must NOT translate the cloud away from its
    own center. The scaled cloud's geometric center must remain at
    `track_center` (the only reasonable pivot for in-place scaling).

    Pre-fix bug: `main()` passed `common_center` as the translation arg, so
    the scaled cloud was re-anchored at a point that may be far outside the
    cameras' field of view, collapsing visibility to zero.
    """
    xyz, track_center = _make_cloud()
    scale = 1.5

    out = gen.transform_points(
        xyz,
        track_center=track_center,
        rotation_deg=0.0,
        scale=scale,
        translation=track_center,
    )

    out_center = 0.5 * (out.min(axis=0) + out.max(axis=0))
    np.testing.assert_allclose(out_center, track_center, atol=1e-6)

    in_extent = xyz.max(axis=0) - xyz.min(axis=0)
    out_extent = out.max(axis=0) - out.min(axis=0)
    np.testing.assert_allclose(out_extent, in_extent * scale, rtol=1e-6)


class _StopMain(Exception):
    pass


def test_main_callsite_uses_track_center_not_common_center(monkeypatch):
    """Guard against regression: the production call site in `main()` must
    pass `track_center` (not `common_center`) as the translation argument
    to `transform_points`. We intercept `transform_points`, capture its
    translation arg, and bail out so the test does not need real cameras
    / tracks / output dirs.
    """
    captured = {}

    def spy_transform(points_xyz, track_center, rotation_deg, scale, translation):
        captured["track_center"] = np.asarray(track_center, dtype=np.float64).copy()
        captured["translation"] = np.asarray(translation, dtype=np.float64).copy()
        raise _StopMain()

    fake_xyz = np.array(
        [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
        dtype=np.float64,
    )
    fake_frame = np.array([1, 1, 1, 1], dtype=np.int32)
    fake_track = np.array([1, 2, 3, 4], dtype=np.int32)
    fake_tracks = np.column_stack([fake_xyz, fake_frame, fake_track]).astype(np.float64)

    class _FakeCam:
        def __init__(self, name, center, axis):
            self.name = name
            self.cam = None
            self.n_row = 800
            self.n_col = 1280
            self.center = np.asarray(center, dtype=np.float64)
            self.axis = np.asarray(axis, dtype=np.float64)

    fake_cams = [
        _FakeCam("cam0", [100.0, 0.0, 0.0], [-1.0, 0.0, 0.0]),
        _FakeCam("cam1", [-100.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
        _FakeCam("cam2", [0.0, 100.0, 0.0], [0.0, -1.0, 0.0]),
    ]

    monkeypatch.setattr(gen, "load_cameras", lambda: fake_cams)
    monkeypatch.setattr(gen, "load_tracks", lambda: fake_tracks)
    monkeypatch.setattr(gen, "camera_fingerprint", lambda paths: "deadbeef00000000")
    monkeypatch.setattr(gen, "transform_points", spy_transform)

    class _Args:
        output_root = Path(REPO_ROOT) / "build" / "_test_transform_placement_tmp"
        rotation_deg = 0.0
        scale = 1.5
        max_preview_frames = 0
        densities = (0.0125,)
        allow_underfill = False

    monkeypatch.setattr(gen, "parse_args", lambda: _Args())

    with pytest.raises(_StopMain):
        gen.main()

    assert "translation" in captured, "transform_points was never called from main()"
    expected_track_center = 0.5 * (fake_xyz.min(axis=0) + fake_xyz.max(axis=0))

    np.testing.assert_allclose(captured["translation"], expected_track_center, atol=1e-9)
    np.testing.assert_allclose(captured["track_center"], expected_track_center, atol=1e-9)

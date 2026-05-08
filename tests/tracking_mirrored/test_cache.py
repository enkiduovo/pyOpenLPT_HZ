"""Narrow tests for the mirrored MAT cache versioning + invalidation logic.

These tests exercise `load_or_build_reflection_cache` and `camera_fingerprint`
in isolation using small synthetic inputs, so they do not require the heavy
SD0075 dataset or the real camera files.
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


def _make_inputs(tmp_path: Path):
    """Build minimal inputs the cache builder needs."""
    transformed_xyz = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [-1.0, -2.0, -3.0],
        ],
        dtype=np.float32,
    )
    vol_min = transformed_xyz.min(axis=0)
    vol_max = transformed_xyz.max(axis=0)

    source_path = tmp_path / "source_tracks.mat"
    source_path.write_bytes(b"\x00" * 64)
    signature = gen.source_signature(source_path)

    cam_dir = tmp_path / "cams"
    cam_dir.mkdir()
    cam_a = cam_dir / "cam0.txt"
    cam_b = cam_dir / "cam1.txt"
    cam_a.write_text("camera-A-content\n")
    cam_b.write_text("camera-B-content\n")
    fingerprint = gen.camera_fingerprint([cam_a, cam_b])

    cache_path = tmp_path / "mirrored_tracks_cache.mat"
    return transformed_xyz, vol_min, vol_max, source_path, signature, cam_dir, fingerprint, cache_path


def test_camera_fingerprint_is_deterministic_and_order_independent(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("alpha")
    b.write_text("beta")
    fp1 = gen.camera_fingerprint([a, b])
    fp2 = gen.camera_fingerprint([b, a])
    assert fp1 == fp2
    assert len(fp1) == 16

    b.write_text("beta-changed")
    fp3 = gen.camera_fingerprint([a, b])
    assert fp3 != fp1, "Changing camera content must change the fingerprint"


def test_cache_miss_then_hit(tmp_path, capsys):
    xyz, vmin, vmax, _src, sig, _cam_dir, fp, cache_path = _make_inputs(tmp_path)

    faces1 = gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, fp, 0.0, 1.5)
    out1 = capsys.readouterr().out
    assert "MISS" in out1 and "does not exist" in out1
    assert cache_path.exists()
    for k in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"):
        assert faces1[k].shape == xyz.shape

    faces2 = gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, fp, 0.0, 1.5)
    out2 = capsys.readouterr().out
    assert "HIT" in out2
    np.testing.assert_array_equal(faces1["x_min"], faces2["x_min"])
    np.testing.assert_array_equal(faces1["z_max"], faces2["z_max"])


def test_cache_invalidates_on_camera_fingerprint_change(tmp_path, capsys):
    xyz, vmin, vmax, _src, sig, _cam_dir, fp, cache_path = _make_inputs(tmp_path)
    gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, fp, 0.0, 1.5)
    capsys.readouterr()

    new_fp = "deadbeefdeadbeef"
    gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, new_fp, 0.0, 1.5)
    out = capsys.readouterr().out
    assert "MISS" in out and "camera files changed" in out


def test_cache_invalidates_on_transform_change(tmp_path, capsys):
    xyz, vmin, vmax, _src, sig, _cam_dir, fp, cache_path = _make_inputs(tmp_path)
    gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, fp, 0.0, 1.5)
    capsys.readouterr()

    gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, fp, 5.0, 1.5)
    out = capsys.readouterr().out
    assert "MISS" in out and "transform parameters changed" in out


def test_cache_invalidates_on_source_signature_change(tmp_path, capsys):
    xyz, vmin, vmax, _src, sig, _cam_dir, fp, cache_path = _make_inputs(tmp_path)
    gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, fp, 0.0, 1.5)
    capsys.readouterr()

    new_sig = (sig[0] + 1, sig[1] + 1)
    gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, new_sig, fp, 0.0, 1.5)
    out = capsys.readouterr().out
    assert "MISS" in out and "source file changed" in out


def test_cache_invalidates_on_version_change(tmp_path, capsys, monkeypatch):
    xyz, vmin, vmax, _src, sig, _cam_dir, fp, cache_path = _make_inputs(tmp_path)
    gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, fp, 0.0, 1.5)
    capsys.readouterr()

    monkeypatch.setattr(gen, "CACHE_VERSION", gen.CACHE_VERSION + 1)
    gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, fp, 0.0, 1.5)
    out = capsys.readouterr().out
    assert "MISS" in out and "version mismatch" in out


def test_cache_face_reflection_math(tmp_path):
    xyz, vmin, vmax, _src, sig, _cam_dir, fp, cache_path = _make_inputs(tmp_path)
    faces = gen.load_or_build_reflection_cache(xyz, vmin, vmax, cache_path, sig, fp, 0.0, 1.5)
    np.testing.assert_allclose(faces["x_min"][:, 0], 2.0 * vmin[0] - xyz[:, 0], atol=1e-5)
    np.testing.assert_allclose(faces["x_max"][:, 0], 2.0 * vmax[0] - xyz[:, 0], atol=1e-5)
    np.testing.assert_allclose(faces["y_min"][:, 1], 2.0 * vmin[1] - xyz[:, 1], atol=1e-5)
    np.testing.assert_allclose(faces["z_max"][:, 2], 2.0 * vmax[2] - xyz[:, 2], atol=1e-5)
    np.testing.assert_allclose(faces["x_min"][:, 1:], xyz[:, 1:], atol=1e-5)
    np.testing.assert_allclose(faces["z_max"][:, :2], xyz[:, :2], atol=1e-5)

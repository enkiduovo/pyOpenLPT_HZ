# pyright: reportAttributeAccessIssue=false
"""Task 7: stable top-level generation_summary.json schema."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

gen = pytest.importorskip("generate_mirrored_tracks")


def _camera(name: str, n_row: int, n_col: int):
    return gen.CameraInfo(name=name, cam=None, n_row=n_row, n_col=n_col, center=np.zeros(3), axis=np.array([0.0, 0.0, 1.0]))


def _dataset_summary(target_ppp: float, feasible: bool):
    return {
        "dataset_dir": f"/tmp/ppp_{target_ppp}",
        "target_ppp": target_ppp,
        "required_active_count": 10,
        "n_frames": 5,
        "selected_track_segments": 7,
        "feasibility": {
            "target_ppp": target_ppp,
            "required_active_count": 10,
            "min_feasible_active_count": 10 if feasible else 5,
            "feasible": feasible,
            "underfill_active_count_shortfall": 0 if feasible else 5,
            "underfill_frames": [] if feasible else [1, 2],
            "allow_underfill": not feasible,
            "message": "ok",
        },
    }


def test_generation_summary_has_stable_top_level_schema():
    cameras = [_camera("cam0", 800, 1280), _camera("cam1", 976, 1024)]
    dataset_summaries = [
        _dataset_summary(0.0125, feasible=True),
        _dataset_summary(0.025, feasible=True),
        _dataset_summary(0.05, feasible=False),
    ]

    summary = gen.build_generation_summary(
        track_mat=Path("/tmp/tracks.mat"),
        camera_dir=Path("/tmp/camFile"),
        output_root=Path("/tmp/mirrored_sampled"),
        cache_path=Path("/tmp/mirrored_sampled/mirrored_tracks_cache.mat"),
        cameras=cameras,
        rotation_deg=0.0,
        scale=1.5,
        track_center=np.array([1.0, 2.0, 3.0]),
        common_center=np.array([4.0, 5.0, 6.0]),
        volume_min=np.array([-10.0, -10.0, -10.0]),
        volume_max=np.array([10.0, 10.0, 10.0]),
        dataset_summaries=dataset_summaries,
    )

    # Required top-level keys (QA scenario expects transform, cache, densities)
    assert set(summary.keys()) >= {
        "schema_version",
        "track_mat",
        "camera_dir",
        "output_root",
        "transform",
        "cameras",
        "cache",
        "feasibility",
        "densities",
    }
    assert summary["schema_version"] == 1

    # Transform metadata grouped, fixed transform values present
    assert summary["transform"]["rotation_deg_about_z"] == 0.0
    assert summary["transform"]["scale"] == 1.5
    assert summary["transform"]["track_center_mm"] == [1.0, 2.0, 3.0]
    assert summary["transform"]["common_center_mm"] == [4.0, 5.0, 6.0]
    assert summary["transform"]["translation_mm"] == [1.0, 2.0, 3.0]

    # Cameras: heterogeneous sizes preserved
    assert summary["cameras"] == {
        "cam0": {"n_row": 800, "n_col": 1280},
        "cam1": {"n_row": 976, "n_col": 1024},
    }

    # Cache section: path + version + volume + faces
    assert summary["cache"]["path"].endswith("mirrored_tracks_cache.mat")
    assert summary["cache"]["version"] == gen.CACHE_VERSION
    assert summary["cache"]["volume_min_mm"] == [-10.0, -10.0, -10.0]
    assert summary["cache"]["volume_max_mm"] == [10.0, 10.0, 10.0]
    assert summary["cache"]["faces"] == ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]

    # Feasibility: top-level list, one entry per density, stable order
    assert [entry["target_ppp"] for entry in summary["feasibility"]] == [0.0125, 0.025, 0.05]
    assert summary["feasibility"][0]["feasible"] is True
    assert summary["feasibility"][2]["feasible"] is False

    # Densities: dataset summaries preserved verbatim, stable order
    assert [entry["target_ppp"] for entry in summary["densities"]] == [0.0125, 0.025, 0.05]


def test_generation_summary_is_json_serializable():
    import json

    cameras = [_camera("cam0", 800, 1280)]
    summary = gen.build_generation_summary(
        track_mat=Path("/tmp/tracks.mat"),
        camera_dir=Path("/tmp/camFile"),
        output_root=Path("/tmp/mirrored_sampled"),
        cache_path=Path("/tmp/mirrored_sampled/mirrored_tracks_cache.mat"),
        cameras=cameras,
        rotation_deg=0.0,
        scale=1.5,
        track_center=np.array([0.0, 0.0, 0.0]),
        common_center=np.array([0.0, 0.0, 0.0]),
        volume_min=np.array([-1.0, -1.0, -1.0]),
        volume_max=np.array([1.0, 1.0, 1.0]),
        dataset_summaries=[_dataset_summary(0.0125, feasible=True)],
    )

    encoded = json.dumps(summary)
    decoded = json.loads(encoded)
    assert decoded["schema_version"] == 1
    assert "densities" in decoded
    assert "transform" in decoded
    assert "cache" in decoded

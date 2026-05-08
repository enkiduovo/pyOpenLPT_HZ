# pyright: reportAttributeAccessIssue=false
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


def _candidate(track_id: int, start_frame: int, end_frame: int):
    return gen.MirroredCandidate(
        track_id=track_id,
        source_track_id=track_id,
        mirror_face=0,
        qualifying_runs=(gen.QualifyingRun(start_frame=start_frame, end_frame=end_frame),),
    )


def test_random_sampling_is_reproducible_for_same_seed():
    candidates = [_candidate(1, 0, 29), _candidate(2, 0, 29), _candidate(3, 0, 29), _candidate(4, 0, 29)]

    first_records, first_mask = gen.select_candidates_for_density(
        candidates,
        n_frames=30,
        target_active_count=2,
        rng=np.random.default_rng(20260422),
    )
    second_records, second_mask = gen.select_candidates_for_density(
        candidates,
        n_frames=30,
        target_active_count=2,
        rng=np.random.default_rng(20260422),
    )

    assert [record["track_id"] for record in first_records] == [record["track_id"] for record in second_records]
    assert len({record["track_id"] for record in first_records}) == 2
    assert first_mask.tolist() == second_mask.tolist()


def test_feasibility_uses_per_camera_image_sizes_and_fails_loudly():
    cameras = [_camera("cam_small", 10, 10), _camera("cam_large", 20, 20)]
    candidates = [_candidate(1, 0, 4), _candidate(2, 0, 4), _candidate(3, 0, 4)]

    report = gen.evaluate_density_feasibility(candidates, n_frames=5, density=0.01, cameras=cameras)

    assert report["target_counts_by_camera"] == {"cam_small": 1, "cam_large": 4}
    assert report["required_active_count"] == 4
    assert report["min_feasible_active_count"] == 3
    assert report["feasible"] is False
    assert report["feasible_ppp_by_camera"]["cam_small"]["min"] == pytest.approx(0.03)
    assert report["feasible_ppp_by_camera"]["cam_large"]["min"] == pytest.approx(0.0075)

    with pytest.raises(RuntimeError, match="Infeasible PPP target"):
        gen.ensure_density_feasibility(report, allow_underfill=False)


def test_underfill_can_be_allowed_but_is_explicit_in_summary():
    cameras = [_camera("cam_small", 10, 10), _camera("cam_large", 20, 20)]
    candidates = [_candidate(1, 0, 4), _candidate(2, 0, 4), _candidate(3, 0, 4)]

    report = gen.evaluate_density_feasibility(candidates, n_frames=5, density=0.01, cameras=cameras)

    message = gen.ensure_density_feasibility(report, allow_underfill=True)

    assert "UNDERFILL ALLOWED" in message
    assert "required_active_count=4" in message
    assert "min_feasible_active_count=3" in message

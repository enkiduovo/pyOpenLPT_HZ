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


def _runs(candidate):
    return [(run.start_frame, run.end_frame) for run in candidate.qualifying_runs]


def test_whole_track_registry_deduplicates_multi_run_candidate():
    visibility = np.zeros((14, 30), dtype=bool)
    visibility[2, 1:11] = True
    visibility[2, 15:27] = True

    candidates = gen.build_whole_track_registry(visibility, max_source_track_id=2)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.track_id == 3
    assert candidate.source_track_id == 1
    assert candidate.mirror_face == 1
    assert _runs(candidate) == [(1, 10), (15, 26)]


def test_whole_track_registry_enforces_ten_frame_threshold():
    visibility = np.zeros((7, 20), dtype=bool)
    visibility[0, 0:9] = True
    visibility[1, 5:15] = True

    candidates = gen.build_whole_track_registry(visibility, max_source_track_id=1)

    assert [candidate.track_id for candidate in candidates] == [2]
    assert candidates[0].source_track_id == 1
    assert candidates[0].mirror_face == 1
    assert _runs(candidates[0]) == [(5, 14)]


def test_candidate_selection_keeps_one_pool_entry_for_multi_run_candidate():
    candidate = gen.MirroredCandidate(
        track_id=3,
        source_track_id=1,
        mirror_face=1,
        qualifying_runs=(
            gen.QualifyingRun(start_frame=1, end_frame=10),
            gen.QualifyingRun(start_frame=15, end_frame=26),
        ),
    )

    selected_records, selected_track = gen.select_candidates_for_density(
        [candidate],
        n_frames=30,
        target_count=1,
        rng=np.random.default_rng(1234),
    )

    assert selected_track.tolist() == [False, False, True]
    assert len(selected_records) == 1
    assert selected_records[0]["track_id"] == 3
    assert selected_records[0]["source_track_id"] == 1
    assert selected_records[0]["mirror_face"] == 1
    assert selected_records[0]["segment_start_frame"] == 2
    assert selected_records[0]["segment_end_frame"] == 11

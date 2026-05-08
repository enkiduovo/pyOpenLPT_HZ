# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy.io import loadmat

try:
    import cv2
except ImportError:  # pragma: no cover - handled at runtime
    cv2 = None


SCHEMA_VERSION = 1
TRACER_RADIUS = 2
ALPHA = 0.0
GAUSS_A = 125.0
GAUSS_B = 0.65
GAUSS_C = 0.65
MIN_INTENSITY = 0.0
MAX_INTENSITY = 255.0
IMAGE_DTYPE = np.uint8
N_CAMERAS = 4
DEFAULT_FRAME_RATE_HZ = 1
DEFAULT_THREADS = 0


@dataclass(frozen=True)
class CameraParameters:
    name: str
    path: Path
    n_row: int
    n_col: int
    cam_matrix: np.ndarray
    dist_coeff: np.ndarray
    rot_vec: np.ndarray
    trans_vec: np.ndarray


def _repo_local_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate deterministic test_STB tracer images and runtime config. "
            "By default, renders the full runtime frame range 0..249. Use --frames START END "
            "for an inclusive subset smoke run. Existing non-empty output directories fail unless "
            "--overwrite is provided."
        )
    )
    parser.add_argument(
        "--mat-path",
        type=Path,
        default=script_dir / "tracks_12k5_coarse_250frames.mat",
        help="Source MAT file containing a 'tracks' array with columns [x,y,z,frame,trackID].",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=script_dir / "generated",
        help="Output directory to create or populate (default: %(default)s).",
    )
    parser.add_argument(
        "--camera-dir",
        type=Path,
        default=script_dir / "camFile",
        help="Directory containing legacy camera txt files (default: %(default)s).",
    )
    parser.add_argument(
        "--tracer-config",
        type=Path,
        default=script_dir / "tracerConfig.txt",
        help="Tracer config source copied into the output root (default: %(default)s).",
    )
    parser.add_argument(
        "--frames",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="Inclusive runtime frame subset to render, e.g. --frames 0 4. Omit for the full 0..249 range.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Remove and recreate the output directory if it already exists.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help=(
            "Replace the original test_STB imgFile/config files in-place instead of writing a generated/ tree. "
            "Requires --overwrite and writes tracking output to ../../results/test_STB/."
        ),
    )
    parser.add_argument(
        "--n-threads",
        type=int,
        default=DEFAULT_THREADS,
        help="Thread count written into config_runtime.txt (default: %(default)s).",
    )
    return parser.parse_args()


def parse_camera_file(path: Path) -> CameraParameters:
    lines = path.read_text(encoding="utf-8").splitlines()[2:]
    line_id = 1

    line_id += 4
    img_size = np.fromstring(lines[line_id], sep=",", dtype=np.int32)
    n_row, n_col = int(img_size[0]), int(img_size[1])

    line_id += 2
    cam_matrix = np.zeros((3, 3), dtype=np.float64)
    for row in range(3):
        cam_matrix[row, :] = np.fromstring(lines[line_id + row], sep=",", dtype=np.float64)

    line_id += 4
    dist_coeff = np.fromstring(lines[line_id], sep=",", dtype=np.float64).reshape(1, -1)

    line_id += 2
    rot_vec = np.fromstring(lines[line_id], sep=",", dtype=np.float64).reshape(3, 1)

    line_id += 10
    trans_vec = np.fromstring(lines[line_id], sep=",", dtype=np.float64).reshape(3, 1)

    return CameraParameters(
        name=path.stem,
        path=path,
        n_row=n_row,
        n_col=n_col,
        cam_matrix=cam_matrix,
        dist_coeff=dist_coeff,
        rot_vec=rot_vec,
        trans_vec=trans_vec,
    )


def load_tracks(mat_path: Path) -> np.ndarray:
    tracks = np.asarray(loadmat(mat_path)["tracks"], dtype=np.float64)
    if tracks.ndim != 2 or tracks.shape[1] != 5:
        raise ValueError(f"Expected tracks array with shape (N,5), got {tracks.shape!r}")
    return tracks


def resolve_frame_range(frames: Sequence[int] | None, total_frames: int) -> tuple[int, int]:
    if total_frames <= 0:
        raise ValueError("total_frames must be positive")
    start, end = (0, total_frames - 1) if frames is None else (int(frames[0]), int(frames[1]))
    if start > end:
        raise ValueError("Frame subset must satisfy START <= END")
    if start < 0 or end >= total_frames:
        raise ValueError(f"Frame subset must stay within 0..{total_frames - 1}")
    return start, end


def prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists():
        entries = list(output_dir.iterdir())
        if entries:
            if not overwrite:
                raise FileExistsError(
                    f"Output directory '{output_dir}' already exists and is not empty. Use --overwrite to replace it."
                )
            shutil.rmtree(output_dir)
        elif overwrite:
            shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def prepare_in_place_output(output_dir: Path, overwrite: bool) -> None:
    if not overwrite:
        raise FileExistsError("In-place regeneration replaces existing imgFile/config files; pass --overwrite to proceed.")
    (output_dir / "imgFile").mkdir(parents=True, exist_ok=True)
    for cam_idx in range(1, N_CAMERAS + 1):
        camera_image_dir = output_dir / "imgFile" / f"cam{cam_idx}"
        if camera_image_dir.exists():
            for image_path in camera_image_dir.glob("*.tif"):
                image_path.unlink()
        camera_image_dir.mkdir(parents=True, exist_ok=True)
        for list_name in (f"cam{cam_idx}ImageNames.txt", f"cam{cam_idx}ImageNames_python.txt"):
            list_path = output_dir / "imgFile" / list_name
            if list_path.exists():
                list_path.unlink()
    for artifact_name in ("manifest.csv", "reference_summary.json", "config_runtime.txt"):
        artifact_path = output_dir / artifact_name
        if artifact_path.exists():
            artifact_path.unlink()


def build_runtime_config_text(
    frame_start: int,
    frame_end: int,
    n_threads: int = DEFAULT_THREADS,
    camera_prefix: str = "../camFile",
    output_path: str = "../../../results/test_STB_generated/",
) -> str:
    camera_lines = "\n".join(f"{camera_prefix}/cam{i}.txt,255" for i in range(1, N_CAMERAS + 1))
    image_lines = "\n".join(f"imgFile/cam{i}ImageNames.txt" for i in range(1, N_CAMERAS + 1))
    return "\n".join(
        [
            "# Frame Range: [startID,endID]",
            f"{frame_start},{frame_end}",
            "# Frame Rate: [Hz]",
            str(DEFAULT_FRAME_RATE_HZ),
            "# Number of Threads: (0: use as many as possible)",
            str(n_threads),
            "# Number of Cameras: ",
            str(N_CAMERAS),
            "# Camera File Path, Max Intensity",
            camera_lines,
            "# Image File Path",
            image_lines,
            "# View Volume: (xmin,xmax,ymin,ymax,zmin,zmax)",
            "-20,20,-20,20,-20,20",
            "# Voxel to MM: e.g. use 1000^3 voxel, (xmax-xmin)/1000",
            "0.04",
            "# Output Folder Path: ",
            output_path,
            "# Object Types: ",
            "Tracer",
            "# STB Config Files:",
            "tracerConfig.txt",
            "# Flag to load previous track files, previous frameID",
            "0,-1",
            "",
        ]
    )


def compute_projection_flags(projection: np.ndarray, n_row: int, n_col: int, tr_radius: int = TRACER_RADIUS) -> tuple[np.ndarray, np.ndarray]:
    u = projection[:, 0]
    v = projection[:, 1]
    finite = np.isfinite(u) & np.isfinite(v)
    visible = finite & (u >= 0.0) & (u < n_col) & (v >= 0.0) & (v < n_row)

    rendered = np.zeros(projection.shape[0], dtype=bool)
    if np.any(finite):
        uf = u[finite]
        vf = v[finite]
        xmin = np.floor(np.maximum(uf - tr_radius, 0.0)).astype(np.int64)
        xmax = np.floor(np.minimum(uf + tr_radius + 1.0, float(n_col))).astype(np.int64)
        ymin = np.floor(np.maximum(vf - tr_radius, 0.0)).astype(np.int64)
        ymax = np.floor(np.minimum(vf + tr_radius + 1.0, float(n_row))).astype(np.int64)
        rendered[finite] = (xmax > xmin) & (ymax > ymin)
    return visible, rendered


def render_image(points_3d: np.ndarray, projection: np.ndarray, n_row: int, n_col: int) -> np.ndarray:
    image = np.zeros((n_row, n_col), dtype=np.float64)
    if points_3d.size == 0:
        return image.astype(IMAGE_DTYPE)

    for idx in range(projection.shape[0]):
        x = float(projection[idx, 0])
        y = float(projection[idx, 1])
        if not (math.isfinite(x) and math.isfinite(y)):
            continue

        xmin = int(math.floor(max(x - TRACER_RADIUS, 0.0)))
        xmax = int(math.floor(min(x + TRACER_RADIUS + 1.0, float(n_col))))
        ymin = int(math.floor(max(y - TRACER_RADIUS, 0.0)))
        ymax = int(math.floor(min(y + TRACER_RADIUS + 1.0, float(n_row))))
        if xmin >= xmax or ymin >= ymax:
            continue

        yy, xx = np.mgrid[ymin:ymax, xmin:xmax]
        kk = (xx - x) * math.cos(ALPHA) + (yy - y) * math.sin(ALPHA)
        jj = -(xx - x) * math.sin(ALPHA) + (yy - y) * math.cos(ALPHA)
        patch = GAUSS_A * np.exp(-GAUSS_B * jj * jj - GAUSS_C * kk * kk)
        patch = np.clip(patch, MIN_INTENSITY, MAX_INTENSITY)
        image[ymin:ymax, xmin:xmax] = np.maximum(image[ymin:ymax, xmin:xmax], patch)

    return image.astype(IMAGE_DTYPE)


def write_image_list(output_dir: Path, camera_name: str, frame_start: int, frame_end: int, suffix: str = "") -> int:
    image_list_path = output_dir / "imgFile" / f"{camera_name}ImageNames{suffix}.txt"
    lines = [f"imgFile/{camera_name}/img{frame_idx:05d}.tif" for frame_idx in range(frame_start, frame_end + 1)]
    image_list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(
    output_dir: Path,
    mat_path: Path,
    camera_dir: Path,
    tracer_config_path: Path,
    frames: Sequence[int] | None,
    overwrite: bool,
    n_threads: int,
    in_place: bool = False,
) -> dict[str, object]:
    if cv2 is None:
        raise RuntimeError("opencv-python (cv2) is required but unavailable in the selected Python environment")

    tracks = load_tracks(mat_path)
    source_frames = tracks[:, 3].astype(np.int64)
    if source_frames.min() != 1:
        raise ValueError(f"Expected source frames to start at 1, got {source_frames.min()}")
    total_frames = int(source_frames.max())
    frame_start, frame_end = resolve_frame_range(frames, total_frames)

    if in_place:
        prepare_in_place_output(output_dir, overwrite)
    else:
        prepare_output_dir(output_dir, overwrite)
        (output_dir / "imgFile").mkdir(parents=True, exist_ok=True)
        for cam_idx in range(1, N_CAMERAS + 1):
            (output_dir / "imgFile" / f"cam{cam_idx}").mkdir(parents=True, exist_ok=True)

    cameras = [parse_camera_file(camera_dir / f"cam{cam_idx}.txt") for cam_idx in range(1, N_CAMERAS + 1)]

    config_text = build_runtime_config_text(
        frame_start,
        frame_end,
        n_threads=n_threads,
        camera_prefix="camFile" if in_place else "../camFile",
        output_path="../../results/test_STB/" if in_place else "../../../results/test_STB_generated/",
    )
    config_paths = [output_dir / "config.txt", output_dir / "config_python.txt"] if in_place else [output_dir / "config_runtime.txt"]
    for config_path in config_paths:
        config_path.write_text(config_text, encoding="utf-8")
    tracer_config_dest = output_dir / "tracerConfig.txt"
    if tracer_config_path.resolve() != tracer_config_dest.resolve():
        shutil.copyfile(tracer_config_path, tracer_config_dest)

    image_list_counts: dict[str, int] = {}
    for camera in cameras:
        image_list_counts[camera.name] = write_image_list(output_dir, camera.name, frame_start, frame_end)
        if in_place:
            write_image_list(output_dir, camera.name, frame_start, frame_end, suffix="_python")

    selected_mask = (source_frames - 1 >= frame_start) & (source_frames - 1 <= frame_end)
    selected_indices = np.flatnonzero(selected_mask)
    selected_tracks = tracks[selected_indices]
    selected_runtime_frames = source_frames[selected_indices] - 1
    within_frame_indices = np.empty(selected_tracks.shape[0], dtype=np.int64)
    for runtime_frame in range(frame_start, frame_end + 1):
        frame_rows = np.flatnonzero(selected_runtime_frames == runtime_frame)
        within_frame_indices[frame_rows] = np.arange(frame_rows.size, dtype=np.int64)

    manifest_path = output_dir / "manifest.csv"
    fieldnames = [
        "mat_row_index",
        "source_frame_1based",
        "runtime_frame_0based",
        "track_id",
        "x",
        "y",
        "z",
    ]
    for cam_idx in range(1, N_CAMERAS + 1):
        fieldnames.extend([f"cam{cam_idx}_u", f"cam{cam_idx}_v", f"cam{cam_idx}_visible", f"cam{cam_idx}_rendered"])

    visible_counts = {camera.name: 0 for camera in cameras}
    rendered_counts = {camera.name: 0 for camera in cameras}
    point_counts_by_frame: dict[str, int] = {}
    projections_by_frame: dict[int, list[np.ndarray]] = {}
    flags_by_frame: dict[int, list[tuple[np.ndarray, np.ndarray]]] = {}

    for runtime_frame in range(frame_start, frame_end + 1):
        frame_indices = np.flatnonzero(selected_runtime_frames == runtime_frame)
        points = selected_tracks[frame_indices, 0:3]
        point_counts_by_frame[str(runtime_frame)] = int(points.shape[0])

        per_camera_projection: list[np.ndarray] = []
        per_camera_flags: list[tuple[np.ndarray, np.ndarray]] = []
        for camera in cameras:
            if points.size == 0:
                projection = np.empty((0, 2), dtype=np.float64)
            else:
                projection = cv2.projectPoints(
                    points.reshape(-1, 1, 3),
                    camera.rot_vec,
                    camera.trans_vec,
                    camera.cam_matrix,
                    camera.dist_coeff,
                )[0].reshape(-1, 2)
            visible, rendered = compute_projection_flags(projection, camera.n_row, camera.n_col)
            visible_counts[camera.name] += int(np.count_nonzero(visible))
            rendered_counts[camera.name] += int(np.count_nonzero(rendered))
            per_camera_projection.append(projection)
            per_camera_flags.append((visible, rendered))
        projections_by_frame[runtime_frame] = per_camera_projection
        flags_by_frame[runtime_frame] = per_camera_flags

    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for relative_index, mat_row_index in enumerate(selected_indices):
            row = selected_tracks[relative_index]
            runtime_frame = int(selected_runtime_frames[relative_index])
            within_frame_index = int(within_frame_indices[relative_index])

            manifest_row: dict[str, object] = {
                "mat_row_index": int(mat_row_index),
                "source_frame_1based": int(row[3]),
                "runtime_frame_0based": runtime_frame,
                "track_id": int(row[4]),
                "x": float(row[0]),
                "y": float(row[1]),
                "z": float(row[2]),
            }
            for cam_idx, camera in enumerate(cameras, start=1):
                projection = projections_by_frame[runtime_frame][cam_idx - 1]
                visible, rendered = flags_by_frame[runtime_frame][cam_idx - 1]
                if projection.shape[0] == 0:
                    u_value = ""
                    v_value = ""
                    visible_value = 0
                    rendered_value = 0
                else:
                    u = float(projection[within_frame_index, 0])
                    v = float(projection[within_frame_index, 1])
                    u_value = u
                    v_value = v
                    visible_value = int(bool(visible[within_frame_index]))
                    rendered_value = int(bool(rendered[within_frame_index]))
                manifest_row[f"cam{cam_idx}_u"] = u_value
                manifest_row[f"cam{cam_idx}_v"] = v_value
                manifest_row[f"cam{cam_idx}_visible"] = visible_value
                manifest_row[f"cam{cam_idx}_rendered"] = rendered_value
            writer.writerow(manifest_row)

    for runtime_frame in range(frame_start, frame_end + 1):
        frame_indices = np.flatnonzero(selected_runtime_frames == runtime_frame)
        points = selected_tracks[frame_indices, 0:3]
        per_camera_projection = projections_by_frame[runtime_frame]
        for camera, projection in zip(cameras, per_camera_projection):
            image = render_image(points, projection, camera.n_row, camera.n_col)
            image_path = output_dir / "imgFile" / camera.name / f"img{runtime_frame:05d}.tif"
            success = cv2.imwrite(str(image_path), image)
            if not success:
                raise RuntimeError(f"Failed to write image '{image_path}'")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "mat_path": _repo_local_path(mat_path),
            "camera_dir": _repo_local_path(camera_dir),
            "tracer_config": _repo_local_path(tracer_config_path),
        },
        "output_path": _repo_local_path(output_dir),
        "frame_range": {"runtime_start": frame_start, "runtime_end": frame_end, "source_start": frame_start + 1, "source_end": frame_end + 1},
        "n_frames": frame_end - frame_start + 1,
        "point_counts": {
            "mat_rows_total": int(tracks.shape[0]),
            "selected_rows": int(selected_tracks.shape[0]),
            "per_runtime_frame": point_counts_by_frame,
        },
        "track_counts": {
            "source_unique": int(np.unique(tracks[:, 4].astype(np.int64)).size),
            "selected_unique": int(np.unique(selected_tracks[:, 4].astype(np.int64)).size),
        },
        "camera_sizes": {camera.name: {"n_row": camera.n_row, "n_col": camera.n_col} for camera in cameras},
        "image_list_counts": image_list_counts,
        "visible_counts_per_camera": visible_counts,
        "rendered_counts_per_camera": rendered_counts,
        "checksums": {
            "manifest_csv_sha256": sha256_file(manifest_path),
            "config_txt_sha256": sha256_file(config_paths[0]),
        },
        "mode": "in_place" if in_place else "generated",
    }

    summary_path = output_dir / "reference_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    output_dir = script_dir if args.in_place else args.output_dir.resolve()
    summary = generate(
        output_dir=output_dir,
        mat_path=args.mat_path.resolve(),
        camera_dir=args.camera_dir.resolve(),
        tracer_config_path=args.tracer_config.resolve(),
        frames=args.frames,
        overwrite=args.overwrite,
        n_threads=args.n_threads,
        in_place=args.in_place,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

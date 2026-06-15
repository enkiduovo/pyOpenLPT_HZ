#!/usr/bin/env python3
"""
Headless tracking SETTINGS CLI.

Drives the SAME `TrackingSettingsView` widget the GUI's "Settings" page uses
(`gui/views/tracking_settings_view.py`), so the generated `config.txt` and
`[type]Config.txt` are byte-identical to clicking "Save Configuration" in the
GUI with the same field values. No tracking/calibration logic is reimplemented.

This is meant for SLURM/cluster pipelines: point it at a project directory and
it writes config.txt + bubbleConfig.txt/tracerConfig.txt, ready for the
tracking step. Run it once per project (or every time before tracking) so you
don't have to open the GUI.

Defaults match the most common bubble-tracking setup:
  --fps 3000  --object-type bubble

Examples
--------
  # Minimal: just point at the project (uses imgFile/, camFile/ inside it)
  python cli_tracking_settings.py /scratch/me/run01

  # Override frame range and a few bubble parameters
  python cli_tracking_settings.py /scratch/me/run01 \\
      --frame-start 0 --frame-end 49931 \\
      --bubble-min-radius 4 --bubble-max-radius 60 --bubble-sensitivity 0.8

  # Tracer run with explicit thread count for a SLURM allocation
  python cli_tracking_settings.py /scratch/me/run01 \\
      --object-type tracer --fps 1000 --n-threads $SLURM_CPUS_PER_TASK

  # Print the config that WOULD be written, without touching disk
  python cli_tracking_settings.py /scratch/me/run01 --dry-run

Notes
-----
- Number of Cameras, Frame End, the View Volume, IPR tolerances, and the
  camera-file list are auto-derived from `<project>/imgFile` and
  `<project>/camFile` exactly as the GUI does (folder/frame counts, camFile
  reprojection stats, etc.) - this is the SAME `_update_paths()` /
  `_on_cam_path_changed()` logic the GUI runs, just invoked here directly.
- Any auto-derived value can still be overridden with the flags below; an
  override is applied AFTER auto-detection, so it always wins.
- Requires PySide6 + qtawesome (same as the GUI) because it reuses the GUI
  widget's logic; it does not open a window (`QT_QPA_PLATFORM=offscreen`).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate config.txt + [type]Config.txt for OpenLPT tracking "
                    "(headless equivalent of the GUI Settings page).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("project_dir", help="Project directory (contains imgFile/ and camFile/)")

    parser.add_argument("--object-type", choices=["bubble", "tracer"], default="bubble",
                        help="Object type (writes bubbleConfig.txt or tracerConfig.txt)")
    parser.add_argument("--fps", type=int, default=3000, help="Frame rate [Hz]")

    # --- Basic ---
    parser.add_argument("--n-cameras", type=int, default=None,
                        help="Number of cameras (default: auto-detect from imgFile/ subfolder count)")
    parser.add_argument("--frame-start", type=int, default=None,
                        help="Start frame (default: 0)")
    parser.add_argument("--frame-end", type=int, default=None,
                        help="End frame (default: auto-detect from image count in the first camera folder, minus 1)")
    parser.add_argument("--n-threads", type=int, default=None,
                        help="Number of threads, 0 = use all available (default: auto, local CPU count - "
                             "set this explicitly to match your SLURM allocation, e.g. $SLURM_CPUS_PER_TASK)")

    # --- Paths ---
    parser.add_argument("--image-path", default=None, help="Image file path (default: <project>/imgFile)")
    parser.add_argument("--camera-path", default=None, help="Camera file path (default: <project>/camFile)")
    parser.add_argument("--output-path", default=None, help="Output/results path (default: <project>/Results)")

    # --- Volume / Voxel ---
    parser.add_argument("--volume", nargs=6, type=float, default=None,
                        metavar=("XMIN", "XMAX", "YMIN", "YMAX", "ZMIN", "ZMAX"),
                        help="View volume bounds (default: auto-estimated from camera files, "
                             "or -200..200 on each axis if no camera files are found)")
    parser.add_argument("--voxel-to-mm", type=float, default=None,
                        help="Voxel-to-mm scale (default: 0.001, or auto-adjusted with --volume/IPR estimation)")

    # --- Resume ---
    parser.add_argument("--resume", action="store_true", help="Set the 'load previous track files' flag")
    parser.add_argument("--resume-frame", type=int, default=None, help="Resume frame ID")

    # --- IPR / Shake / STB (advanced; all optional overrides) ---
    parser.add_argument("--ipr-2d-tol", type=float, default=None, help="2D tolerance [px] (default: auto/2.0)")
    parser.add_argument("--ipr-3d-tol", type=float, default=None, help="3D tolerance [voxel] (default: auto/1.0)")
    parser.add_argument("--ipr-loops", type=int, default=None, help="Number of IPR loops (default: 4)")
    parser.add_argument("--ipr-reduce-cam", type=int, default=None, help="Number of reduced cameras (default: 1)")
    parser.add_argument("--ipr-reduced-loops", type=int, default=None,
                        help="IPR loops per reduced-camera combination (default: 2)")
    parser.add_argument("--shake-width", type=float, default=None, help="Shake width (default: 0.25)")
    parser.add_argument("--shake-loops", type=int, default=None, help="Number of shake loops (default: 4)")
    parser.add_argument("--shake-ghost-thresh", type=float, default=None, help="Ghost threshold (default: 0.01)")
    parser.add_argument("--stb-initial-radius", type=float, default=None,
                        help="Initial-phase search radius (default: 10.0)")
    parser.add_argument("--stb-initial-frames", type=int, default=None,
                        help="Number of initial-phase frames (default: 4)")
    parser.add_argument("--stb-avg-spacing", type=float, default=None,
                        help="Avg interparticle spacing [voxel] (default: 30.0)")
    parser.add_argument("--pred-grid", nargs=3, type=int, default=None, metavar=("X", "Y", "Z"),
                        help="Predictive field grid size (default: 51 51 51)")
    parser.add_argument("--pred-search-radius", type=float, default=None,
                        help="Predictive field search radius [voxel] (default: 25.0)")

    # --- Tracer-specific ---
    parser.add_argument("--tracer-int-thresh", type=int, default=None,
                        help="Tracer 2D intensity threshold (default: 30)")
    parser.add_argument("--tracer-radius", type=float, default=None, help="Tracer radius [px] (default: 2.0)")

    # --- Bubble-specific ---
    parser.add_argument("--bubble-min-radius", type=float, default=None, help="Minimum bubble radius [px] (default: 5.0)")
    parser.add_argument("--bubble-max-radius", type=float, default=None, help="Maximum bubble radius [px] (default: 50.0)")
    parser.add_argument("--bubble-sensitivity", type=float, default=None, help="Bubble detection sensitivity (default: 0.8)")

    parser.add_argument("--dry-run", action="store_true",
                        help="Print the config files that would be written, without saving them")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir).expanduser().resolve()
    if not project_dir.is_dir():
        parser.error(f"project_dir does not exist or is not a directory: {project_dir}")

    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication([])

    # Headless: GUI dialogs become no-ops (status is reported on stdout instead).
    QMessageBox.warning = staticmethod(lambda *a, **k: None)
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.critical = staticmethod(lambda *a, **k: None)

    from gui.views.tracking_settings_view import TrackingSettingsView

    view = TrackingSettingsView()

    # 1) Point at the project; this triggers the same auto-detection the GUI
    #    runs (image/camera paths, camera count, frame end, volume, IPR tol.)
    view.project_path.setText(str(project_dir))
    view._update_paths()

    # 2) Always-set values (with the requested defaults)
    obj_label = "Bubble" if args.object_type == "bubble" else "Tracer"
    idx = view.obj_type_combo.findText(obj_label)
    if idx >= 0:
        view.obj_type_combo.setCurrentIndex(idx)
    view._update_object_tab(view.obj_type_combo.currentIndex())
    view.fps_spin.setValue(int(args.fps))

    # 3) Path overrides (applied before re-deriving camera-dependent values)
    if args.image_path:
        view.image_path_display.setText(str(Path(args.image_path).expanduser().resolve()))
    if args.camera_path:
        view.camera_path_display.setText(str(Path(args.camera_path).expanduser().resolve()))
        view._on_cam_path_changed()
    if args.output_path:
        view.output_path.setText(str(Path(args.output_path).expanduser().resolve()))

    # 4) Basic overrides
    if args.n_cameras is not None:
        view.n_cam_spin.setValue(int(args.n_cameras))
    if args.frame_start is not None:
        view.frame_start_spin.setValue(int(args.frame_start))
    if args.frame_end is not None:
        view.frame_end_spin.setValue(int(args.frame_end))
    if args.n_threads is not None:
        view.n_threads_spin.setValue(int(args.n_threads))

    # 5) Volume / voxel
    if args.volume is not None:
        xmin, xmax, ymin, ymax, zmin, zmax = args.volume
        view.vol_x_min.setValue(xmin)
        view.vol_x_max.setValue(xmax)
        view.vol_y_min.setValue(ymin)
        view.vol_y_max.setValue(ymax)
        view.vol_z_min.setValue(zmin)
        view.vol_z_max.setValue(zmax)
    if args.voxel_to_mm is not None:
        view.voxel_spin.setValue(args.voxel_to_mm)

    # 6) Resume
    if args.resume:
        view.resume_check.setChecked(True)
    if args.resume_frame is not None:
        view.resume_frame_spin.setValue(int(args.resume_frame))

    # 7) IPR / Shake / STB overrides
    if args.ipr_2d_tol is not None:
        view.ipr_2d_tol.setValue(args.ipr_2d_tol)
    if args.ipr_3d_tol is not None:
        view.ipr_3d_tol.setValue(args.ipr_3d_tol)
    if args.ipr_loops is not None:
        view.ipr_loop_spin.setValue(int(args.ipr_loops))
    if args.ipr_reduce_cam is not None:
        view.ipr_reduce_spin.setValue(int(args.ipr_reduce_cam))
    if args.ipr_reduced_loops is not None:
        view.ipr_reduced_spin.setValue(int(args.ipr_reduced_loops))
    if args.shake_width is not None:
        view.shake_width.setValue(args.shake_width)
    if args.shake_loops is not None:
        view.shake_loops.setValue(int(args.shake_loops))
    if args.shake_ghost_thresh is not None:
        view.shake_ghost.setValue(args.shake_ghost_thresh)
    if args.stb_initial_radius is not None:
        view.stb_initial_radius.setValue(args.stb_initial_radius)
    if args.stb_initial_frames is not None:
        view.stb_initial_frames.setValue(int(args.stb_initial_frames))
    if args.stb_avg_spacing is not None:
        view.stb_avg_spacing.setValue(args.stb_avg_spacing)
    if args.pred_grid is not None:
        gx, gy, gz = args.pred_grid
        view.pred_grid_x.setValue(int(gx))
        view.pred_grid_y.setValue(int(gy))
        view.pred_grid_z.setValue(int(gz))
    if args.pred_search_radius is not None:
        view.pred_search_radius.setValue(args.pred_search_radius)

    # 8) Object-specific overrides
    if args.object_type == "tracer":
        if args.tracer_int_thresh is not None:
            view.tracer_int_thresh.setValue(int(args.tracer_int_thresh))
        if args.tracer_radius is not None:
            view.tracer_radius.setValue(args.tracer_radius)
    else:
        if args.bubble_min_radius is not None:
            view.bubble_min_rad.setValue(args.bubble_min_radius)
        if args.bubble_max_radius is not None:
            view.bubble_max_rad.setValue(args.bubble_max_radius)
        if args.bubble_sensitivity is not None:
            view.bubble_sens.setValue(args.bubble_sensitivity)

    n_cams = view.n_cam_spin.value()
    print(f"Project: {project_dir}")
    print(f"  Image path:  {view.image_path_display.text()}")
    print(f"  Camera path: {view.camera_path_display.text()}")
    print(f"  Output path: {view.output_path.text() or '(default: <project>/Results)'}")
    print(f"  Cameras: {n_cams}, Frames: {view.frame_start_spin.value()}-{view.frame_end_spin.value()}, "
          f"FPS: {view.fps_spin.value()}, Object: {view.obj_type_combo.currentText()}")
    print(f"  Volume: x[{view.vol_x_min.value()},{view.vol_x_max.value()}] "
          f"y[{view.vol_y_min.value()},{view.vol_y_max.value()}] "
          f"z[{view.vol_z_min.value()},{view.vol_z_max.value()}], voxel_to_mm={view.voxel_spin.value()}")
    print(f"  IPR tol: 2D={view.ipr_2d_tol.value()}px, 3D={view.ipr_3d_tol.value()}voxel")

    stb_config_name = "tracerConfig.txt" if args.object_type == "tracer" else "bubbleConfig.txt"

    if args.dry_run:
        print(f"\n[dry-run] Would write {project_dir / 'config.txt'} and "
              f"{project_dir / stb_config_name} (not written).")
        return 0

    view._save_configuration()

    cfg_path = project_dir / "config.txt"
    stb_path = project_dir / stb_config_name

    # The GUI's "Number of Threads" spinbox range is 1..128, so it cannot
    # represent the documented "0 = use all available threads" sentinel
    # (see inc/libSTB/Config.h: `_n_thread = 0` means "use all threads",
    # and Config.cpp clamps negative values to 0). Patch it in afterwards
    # so --n-threads 0 round-trips correctly.
    if args.n_threads == 0 and cfg_path.exists():
        lines = cfg_path.read_text().splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith("# Number of Threads"):
                lines[i + 1] = "0\n"
                break
        cfg_path.write_text("".join(lines))

    if cfg_path.exists() and stb_path.exists():
        print(f"\nWrote {cfg_path}")
        print(f"Wrote {stb_path}")
        return 0

    print("\nERROR: config files were not written. Check that project_dir is a valid "
          "directory and writable.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

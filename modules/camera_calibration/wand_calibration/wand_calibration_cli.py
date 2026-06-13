"""
HZ_fix: Command-line equivalent of the Wand Calibration "Run Calibration" button.

The GUI's Calibration-page "Generate CLI" button writes a single-line command into
``Calibration_CLI.txt`` (next to the wand-points CSV). Copy that line into a
terminal and it runs the same calibration the "Run Calibration" button runs:
it loads the wand-points CSV produced by the point-detection step, applies the
Calibration-page settings (camera model, wand length, distortion, per-camera
focal/image size, and — for refraction — windows and media), runs the matching
calibration pipeline and writes the resulting ``camFile/cam<N>.txt`` files.

Both camera models are supported, matching the UI choice:

- **Pinhole** -> ``WandCalibrator.calibrate_wand`` + ``export_to_file``.
- **Pinhole+Refraction** (``--camera-model refraction``) ->
  ``RefractiveWandCalibrator.calibrate`` (same pipeline as the GUI worker), which
  writes the cam files itself.

Run (one line, as written into ``Calibration_CLI.txt``)::

    # Pinhole
    python "<repo>/modules/camera_calibration/wand_calibration/wand_calibration_cli.py" \\
        --points "<wand_points.csv>" --wand-length 10.0 --distortion 0 \\
        --camera-model pinhole --output "<out_dir>" \\
        --cam "0,9000,1280,800" --cam "1,9000,1280,800"

    # Pinhole+Refraction
    python ".../wand_calibration_cli.py" --points "<wand_points.csv>" \\
        --wand-length 10.0 --distortion 0 --camera-model refraction \\
        --output "<out_dir>" --cam "0,9000,1280,800" --cam "1,9000,1280,800" \\
        --num-windows 1 --cam-window "0:0" --cam-window "1:0" \\
        --window-media "0:1.0,1.49,1.33,10.0"
"""

import sys

import argparse
from pathlib import Path

try:
    # Normal package import (python -m ...).
    from .wand_calibrator import WandCalibrator
except ImportError:  # pragma: no cover - fallback when run as a loose script.
    _REPO_ROOT = Path(__file__).resolve().parents[3]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from modules.camera_calibration.wand_calibration.wand_calibrator import (
        WandCalibrator,
    )


# --------------------------------------------------------------------------- #
# One-line command string (used by the GUI to write the .txt)                 #
# --------------------------------------------------------------------------- #
def build_cli_command(points_csv, wand_length, distortion, camera_model,
                      camera_settings, output_dir, python_exe=None,
                      num_windows=None, cam_to_window=None, window_media=None):
    """Return the single-line command that reproduces 'Run Calibration'.

    camera_settings : dict[int, dict] with keys 'focal', 'width', 'height'.
    For ``camera_model == "refraction"`` also pass ``num_windows``,
    ``cam_to_window`` ({cam_id: window_id}) and ``window_media``
    ({window_id: {'n1','n2','n3','thickness'}}).
    """
    python_exe = python_exe or sys.executable or "python"
    script = Path(__file__).resolve()
    parts = [
        f'"{python_exe}"',
        f'"{script}"',
        f'--points "{points_csv}"',
        f'--wand-length {wand_length}',
        f'--distortion {distortion}',
        f'--camera-model {camera_model}',
        f'--output "{output_dir}"',
    ]
    for cam_id in sorted(camera_settings.keys()):
        s = camera_settings[cam_id]
        parts.append(
            f'--cam "{cam_id},{int(s["focal"])},{int(s["width"])},{int(s["height"])}"'
        )

    if camera_model == "refraction":
        if num_windows is not None:
            parts.append(f'--num-windows {int(num_windows)}')
        for cid in sorted((cam_to_window or {}).keys()):
            parts.append(f'--cam-window "{cid}:{int(cam_to_window[cid])}"')
        for wid in sorted((window_media or {}).keys()):
            m = window_media[wid]
            parts.append(
                f'--window-media "{wid}:{m["n1"]},{m["n2"]},{m["n3"]},{m["thickness"]}"'
            )

    return " ".join(parts)


def _parse_cam_arg(value):
    """Parse a '--cam id,focal,width,height' value into (id, dict)."""
    fields = [f.strip() for f in value.split(",")]
    if len(fields) != 4:
        raise argparse.ArgumentTypeError(
            f"--cam expects 'id,focal,width,height', got: {value!r}"
        )
    cam_id = int(fields[0])
    return cam_id, {
        "focal": float(fields[1]),
        "width": int(fields[2]),
        "height": int(fields[3]),
    }


def _parse_cam_window_arg(value):
    """Parse a '--cam-window cid:wid' value into (cam_id, window_id)."""
    try:
        cid, wid = value.split(":")
        return int(cid), int(wid)
    except Exception:
        raise argparse.ArgumentTypeError(
            f"--cam-window expects 'cam_id:window_id', got: {value!r}"
        )


def _parse_window_media_arg(value):
    """Parse '--window-media wid:n1,n2,n3,thickness' into (wid, media_dict)."""
    try:
        wid_str, rest = value.split(":")
        n1, n2, n3, thick = (float(x) for x in rest.split(","))
    except Exception:
        raise argparse.ArgumentTypeError(
            f"--window-media expects 'wid:n1,n2,n3,thickness', got: {value!r}"
        )
    return int(wid_str), {"n1": n1, "n2": n2, "n3": n3, "thickness": thick}


# --------------------------------------------------------------------------- #
# Driver: run the same calibrate_wand the GUI worker runs                      #
# --------------------------------------------------------------------------- #
def run_calibration(points_csv, camera_settings, wand_length, distortion,
                    camera_model="pinhole", output_dir=None, init_focal=None,
                    num_windows=None, cam_to_window=None, window_media=None):
    """Load points and run calibration, writing cam<N>.txt files.

    Dispatches to the pinhole or the refractive (Pinhole+Refraction) pipeline
    based on ``camera_model``. Returns (success, message, output_paths).
    """
    if not camera_settings:
        return False, "No camera settings provided (use --cam id,focal,width,height).", []

    if camera_model == "refraction":
        return run_refractive_calibration(
            points_csv, camera_settings, wand_length, distortion,
            num_windows, cam_to_window, window_media,
            output_dir=output_dir, init_focal=init_focal,
        )

    # --- Pinhole ---
    calib = WandCalibrator()

    ok, msg = calib.load_wand_data_from_csv(str(points_csv))
    if not ok:
        return False, f"Failed to load points CSV: {msg}", []
    if not getattr(calib, "wand_points", None):
        return False, "No valid frames loaded from the points CSV.", []

    # Mirror what _run_wand_calibration sets on the calibrator.
    first_cam = camera_settings[sorted(camera_settings.keys())[0]]
    calib.image_size = (int(first_cam["height"]), int(first_cam["width"]))
    calib.camera_settings = camera_settings
    calib.dist_coeff_num = int(distortion)
    if init_focal is None:
        init_focal = float(first_cam["focal"])

    print(f"Loaded {len(calib.wand_points)} frames from {points_csv}")
    print(f"Cameras    : {sorted(camera_settings.keys())}")
    print(f"Settings   : model=pinhole, wand_length={wand_length}, "
          f"distortion={distortion}, init_focal={init_focal}, "
          f"image_size={calib.image_size}")

    try:
        success, msg, _res = calib.calibrate_wand(
            wand_length=float(wand_length), init_focal_length=float(init_focal),
        )
    except Exception as exc:
        return False, f"Calibration error: {exc}", []
    if not success:
        return False, f"Calibration failed: {msg}", []

    out_dir = Path(output_dir) if output_dir else Path(points_csv).resolve().parent
    cam_file_dir = out_dir / "camFile"
    cam_file_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for cam_id in calib.final_params.keys():
        path = cam_file_dir / f"cam{cam_id}.txt"
        calib.export_to_file(cam_id, str(path))
        paths.append(str(path))

    return True, f"{msg}. Wrote {len(paths)} camera file(s).", paths


def run_refractive_calibration(points_csv, camera_settings, wand_length,
                               distortion, num_windows, cam_to_window,
                               window_media, output_dir=None, init_focal=None):
    """Run the Pinhole+Refraction calibration (same pipeline as the GUI).

    Mirrors ``RefractiveCalibWorker`` / ``_run_refractive_wand_calibration``:
    builds a base ``WandCalibrator`` from the CSV, then drives
    ``RefractiveWandCalibrator.calibrate(...)`` which writes camFile/cam<N>.txt.
    """
    if not num_windows or not cam_to_window or not window_media:
        return False, ("Refraction model requires --num-windows, --cam-window and "
                       "--window-media."), []

    try:
        from .refraction_wand_calibrator import RefractiveWandCalibrator
    except ImportError:  # run as a loose script (no package context)
        from modules.camera_calibration.wand_calibration.refraction_wand_calibrator import (
            RefractiveWandCalibrator,
        )

    base = WandCalibrator()
    ok, msg = base.load_wand_data_from_csv(str(points_csv))
    if not ok:
        return False, f"Failed to load points CSV: {msg}", []
    if not getattr(base, "wand_points", None):
        return False, "No valid frames loaded from the points CSV.", []

    active_cam_ids = sorted(camera_settings.keys())
    first_cam = camera_settings[active_cam_ids[0]]
    if init_focal is None:
        init_focal = float(first_cam["focal"])

    # Set the same attributes the GUI sets on the calibrator / mock base.
    base.image_size = (int(first_cam["height"]), int(first_cam["width"]))
    base.camera_settings = camera_settings
    base.dist_coeff_num = int(distortion)
    base.wand_length = float(wand_length)
    base.initial_focal = float(init_focal)
    base.active_cam_ids = active_cam_ids
    base.cam_params = {}
    base.cameras = {cid: {} for cid in active_cam_ids}

    out_dir = Path(output_dir) if output_dir else Path(points_csv).resolve().parent
    out_path = str(out_dir / "camFile")

    print(f"Loaded {len(base.wand_points)} frames from {points_csv}")
    print(f"Cameras    : {active_cam_ids}")
    print(f"Settings   : model=refraction, wand_length={wand_length}, "
          f"distortion={distortion}, init_focal={init_focal}, "
          f"image_size={base.image_size}")
    print(f"Windows    : {num_windows}, cam->window={cam_to_window}")

    calibrator = RefractiveWandCalibrator(base)
    try:
        success, _cam_params, _report, _dataset = calibrator.calibrate(
            num_windows=int(num_windows),
            cam_to_window=cam_to_window,
            window_media=window_media,
            out_path=out_path,
            verbosity=1,
            progress_callback=None,
            use_proj_residuals=False,
        )
    except Exception as exc:
        return False, f"Refractive calibration error: {exc}", []
    if not success:
        return False, "Refractive calibration failed.", []

    cam_file_dir = Path(out_path)
    paths = sorted(str(p) for p in cam_file_dir.glob("cam*.txt")) if cam_file_dir.exists() else []
    return True, f"Refractive calibration done. Wrote {len(paths)} camera file(s).", paths


# --------------------------------------------------------------------------- #
# CLI entry point                                                             #
# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="OpenLPT Wand Calibration (CLI equivalent of the GUI "
                    "'Run Calibration' button, pinhole model)."
    )
    parser.add_argument("--points", required=True,
                        help="Wand-points CSV from the point-detection step.")
    parser.add_argument("--wand-length", type=float, default=10.0)
    parser.add_argument("--distortion", type=int, default=0, choices=[0, 1, 2],
                        help="Distortion params: 0=None, 1=k1, 2=k1+k2.")
    parser.add_argument("--camera-model", default="pinhole",
                        choices=["pinhole", "refraction"])
    parser.add_argument("--cam", action="append", default=[], type=_parse_cam_arg,
                        metavar="id,focal,width,height",
                        help="Per-camera settings; repeat for each camera.")
    parser.add_argument("--init-focal", type=float, default=None,
                        help="Initial focal length (default: first camera's focal).")
    parser.add_argument("--output", default=None,
                        help="Output directory (a 'camFile' subfolder is created; "
                             "default: the points CSV's folder).")
    # Refraction-only options.
    parser.add_argument("--num-windows", type=int, default=None,
                        help="(refraction) Number of refraction windows.")
    parser.add_argument("--cam-window", action="append", default=[],
                        type=_parse_cam_window_arg, metavar="cam_id:window_id",
                        help="(refraction) Camera->window mapping; repeat per camera.")
    parser.add_argument("--window-media", action="append", default=[],
                        type=_parse_window_media_arg,
                        metavar="wid:n1,n2,n3,thickness",
                        help="(refraction) Per-window media; repeat per window.")
    args = parser.parse_args(argv)

    points = Path(args.points)
    if not points.exists():
        print(f"Error: points CSV not found: {points}")
        return 1

    camera_settings = {cam_id: s for cam_id, s in args.cam}
    cam_to_window = {cid: wid for cid, wid in args.cam_window}
    window_media = {wid: media for wid, media in args.window_media}

    success, msg, paths = run_calibration(
        points, camera_settings, args.wand_length, args.distortion,
        camera_model=args.camera_model, output_dir=args.output,
        init_focal=args.init_focal,
        num_windows=args.num_windows, cam_to_window=cam_to_window,
        window_media=window_media,
    )
    print(msg)
    for p in paths:
        print(f"  {p}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

# HZ_fix — Change Log

This file records customizations (HZ fixes) made on top of the upstream OpenLPT
codebase. No detection / calibration algorithms are modified — these are UI /
workflow conveniences only.

---

## Summary of changes

### Files changed
- `modules/camera_calibration/view.py` — all UI changes (buttons, camera grid,
  config import/export, CLI generation).
- `modules/camera_calibration/widgets.py` — `SimpleSlider` (Sensitivity) gains an
  editable numeric input.
- `modules/camera_calibration/wand_calibration/point_detection_cli.py` — **new**:
  CLI equivalent of "Process All Frames".
- `modules/camera_calibration/wand_calibration/wand_calibration_cli.py` — **new**:
  CLI equivalent of "Run Calibration" (pinhole **and** Pinhole+Refraction).
- `modules/image_preprocessing/cli.py` — fixed camera-ID convention (now
  0-based, matching the calibration/tracking convention everywhere else).
- `modules/image_preprocessing/runner.py` — fixed image-list filename to
  `cam<N>ImageNames.txt` (matches what the tracking page actually reads).
- `cli_tracking_settings.py` — **new**: CLI equivalent of the Settings page's
  "Save Configuration" (writes `config.txt` + `bubbleConfig.txt`/
  `tracerConfig.txt`).
- `modules/image_preprocessing/reference_frame.py` — **new**: block-based
  coarse-to-fine search for a valid bubble *reference frame* (validation injected,
  never modified). Includes `find_reference_frame` (stride),
  `find_reference_frame_blocks` (hierarchical fps/5 blocks gated by a cheap
  `count_3d` probe), and `make_stereomatch_count3d_proxy` (single-StereoMatch
  proxy that does **not** touch the validator).
- `modules/image_preprocessing/cli.py` — added `find_reference_frame_from_detected`
  (wires the search to the frames `_build_tasks_from_input_root` enumerates).
- `tests/test_image_preprocessing_cli.py`,
  `tests/test_image_preprocessing_io.py` — updated expected filenames/camera
  IDs for the above fix.
- `tests/test_reference_frame_search.py` — **new**: tests for the search.

### `modules/camera_calibration/view.py`
**Changed:**
- `ZoomableImageLabel` — added `clicked` signal + `_left_press_pos`; emits
  `clicked` on a simple left-click in NAV mode (`__init__`, `mousePressEvent`,
  `mouseReleaseEvent`).
- `CameraCalibrationView.__init__` — added `self.GENERATE_CLI_BTN_STYLE`.
- `create_wand_tab_v2()` — added the "Auto-Load Cameras from Root (T0)" button +
  info label; rebuilt the visualization area into a "Cams" grid + "3D View"
  (`QStackedWidget`); added "Generate CLI" (Point Detection); added "Config Load"
  section and "Generate CLI" (Calibration) on the Cal tab.
- `_update_wand_table()` — now calls `_build_cam_vis_grid()` instead of per-camera
  tabs.
- `_load_wand_root_folder()` (referenced helper) — stores `self.wand_root_dir` /
  `self.wand_t0_dir`.
- `_focus_axis_camera()` and the detection-display switch — use `_show_cam_in_vis`
  instead of `vis_tabs.setCurrentIndex(cam_idx)`.

**Added:**
- `_build_cam_vis_grid()`, `_on_cam_label_clicked()`, `_collapse_cam_view()`,
  `_show_cam_in_vis()` — 2-column camera grid + click-to-expand/collapse.
- `_load_wand_root_folder()`, `_set_root_folder_info()` — Root-folder auto-load.
- `_generate_point_detection_cli()` — write one-line "Process All" command.
- `_generate_calibration_cli()` — write one-line "Run Calibration" command.
- `_wand_cam_folders()` — resolve cam folders from loaded images.
- `_collect_cal_config()`, `_apply_cal_config()`, `_export_cal_config()`,
  `_import_cal_config()` — Cal-page config import/export.
- `_browse_wand_output_path()` — pick the detection-results CSV for the new
  "Output Path" section (Change 7).
- `_show_error_matrix()` — "Error Matrix" popup (per-camera mean/median/tail-%
  stats + full frame x camera matrix), Change 13.

### `modules/camera_calibration/widgets.py`
- `SimpleSlider.__init__` — replaced the read-only label with an editable
  `QDoubleSpinBox` (narrow, no spin arrows).
- **Added** `SimpleSlider._set_spin_silently()`, `SimpleSlider._on_spin_changed()`;
  updated `setValue()` and `_SimpleSliderCanvas._update_value()` to keep slider and
  spinbox in sync.

### `modules/camera_calibration/wand_calibration/point_detection_cli.py` (new)
- `discover_cam_folders()`, `list_cam_images()`, `build_image_paths_dict()`,
  `build_cli_command()`, `run_process_all()`, `main()`.

### `modules/camera_calibration/wand_calibration/wand_calibration_cli.py` (new)
- `build_cli_command()`, `_parse_cam_arg()`, `_parse_cam_window_arg()`,
  `_parse_window_media_arg()`, `run_calibration()` (dispatches by model),
  `run_refractive_calibration()`, `main()`.

---

## 1. "Auto-Load Cameras from Root (T0)" button on the Point Detection page (Wand Calibration)

**Date:** 2026-06-12
**File:** `modules/camera_calibration/view.py`
**Tab builder:** `CameraCalibrationView.create_wand_tab_v2()` (the only wand tab
builder actually used — wired up at the `Wand Calibration` tab, see
`self.tabs.addTab(self.create_wand_tab_v2(), "Wand Calibration")`).

### What it does

Adds a button labeled **"Auto-Load Cameras from Root (T0)"** directly above the
**"Camera Images:"** section on the **Point Detection** sub-tab of the Wand
Calibration page, with an **info/status line** beneath it.

The info line starts with a hint ("Pick a root folder that contains a 'T0'
subfolder with 'cam0', 'cam1', … folders. Num Cameras updates automatically.")
and, after a load, is updated in place to show the result — e.g.
`Loaded 6/6 cameras (cam0, cam1, …) from <root>/T0. Num Cameras = 6.` It turns
green on success and red on a problem (no `T0`, no `cam<N>` folders, or a cam
folder with no images).

When clicked:

1. Opens a directory chooser to pick a **root folder**.
2. Looks for a **`T0`** subfolder inside that root folder (case-insensitive).
3. Inside `T0`, finds every folder named **`cam<N>`** (`cam0`, `cam1`, `cam2`,
   … — matched case-insensitively via regex `^cam(\d+)$`) and sorts them in
   **ascending numeric order** by `<N>`.
4. If the number of `cam` folders found differs from the current **Num Cameras**
   value, the **Num Cameras** spinbox is automatically updated to the number of
   `cam` folders found. So if more than 4 cameras are present, the camera count
   grows accordingly (and if fewer, it shrinks).
5. Each `cam<N>` folder's images are loaded into the corresponding camera slot
   (in ascending order), reading image files with extensions
   `.png/.jpg/.jpeg/.bmp/.tif`.
6. Per-camera width/height are auto-filled from the first image (reusing the
   existing `_update_wand_cam_size_from_first_image`), the radius range limit is
   refreshed, and the frame list is repopulated — exactly the same downstream
   wiring as the existing per-camera "Load" buttons.

A summary message box reports how many camera folders were loaded. Warning
dialogs are shown if no `T0` folder or no `cam<N>` folders are found.

### Expected folder layout

```
<root folder>/
└── T0/
    ├── cam0/   (or cam1 — any 'cam' + number)
    │   ├── frame_0001.tif
    │   ├── frame_0002.tif
    │   └── ...
    ├── cam1/
    │   └── ...
    ├── cam2/
    └── cam3/   (more than 4 is supported)
```

`cam` folders are mapped to camera slots in ascending numeric order: the lowest
`<N>` becomes Cam 0 in the table, the next becomes Cam 1, and so on.

### Code changes

- **New button + info label** added in `create_wand_tab_v2()` just before the
  `det_layout.addWidget(QLabel("Camera Images:"))` line:
  `self.btn_load_root_folder` → connected to `self._load_wand_root_folder`, and
  `self.root_folder_info` (a wrapped `QLabel` status line).
- **New method** `_load_wand_root_folder(self, checked=False)` added just before
  `_load_wand_folder_for_cam`. It reuses existing helpers
  (`_update_wand_table`, `_update_wand_cam_size_from_first_image`,
  `_refresh_wand_radius_range_limit`, `populate_wand_table`) so behavior stays
  consistent with manual loading.
- **New helper** `_set_root_folder_info(self, text, error=False)` updates the
  status line text/color (green on success, red on error).

### Notes / guarantees

- **No algorithm changes.** Detection, triangulation, and calibration logic are
  untouched. This only automates the file-selection step that the user would
  otherwise do one camera at a time.
- Setting **Num Cameras** triggers the existing `_update_wand_table`, which
  rebuilds the camera table and visualization grid and resets `wand_images`.
  When the count is unchanged, the method calls `_update_wand_table` explicitly
  so stale image lists are cleared before reloading.

---

## 2. "Cams" grid + expand/collapse in the visualization area (Wand Calibration)

**Date:** 2026-06-12
**File:** `modules/camera_calibration/view.py`
**Tab builder:** `CameraCalibrationView.create_wand_tab_v2()`

### What it does

Replaces the old left-side visualization nav bar — which had one tab per camera
(`Cam 1`, `Cam 2`, … `Cam N`) plus a `3D View` tab — with just **two** tabs:

- **"Cams"** — all cameras shown together in a **2-column grid** (cam0 top-left,
  cam1 top-right, cam2 next row, …). 4 cameras → a 2×2 grid. With **more than 4
  cameras the grid scrolls vertically** (each cell has a minimum size, and the
  grid lives inside a `QScrollArea`).
- **"3D View"** — unchanged (the `Calibration3DViewer`).

**Click to expand / collapse:** clicking any camera in the grid expands that
single camera to fill the whole visualization area. Clicking it again — or the
**"← Back to grid"** button shown above the expanded image — returns to the
2-column grid.

### How it works

- The "Cams" tab holds a `QStackedWidget` (`self.cams_stack`):
  - **page 0** = the scrollable grid (`self.cam_grid_layout`, a `QGridLayout`),
  - **page 1** = the expanded single-camera view (with the "← Back to grid"
    button and `self.cam_expanded_layout`).
- Expanding reparents the clicked `ZoomableImageLabel` into the expanded page and
  switches the stack to page 1; collapsing moves it back to its `(row, col)` slot
  (`row = idx // 2`, `col = idx % 2`) and returns to page 0.
- `ZoomableImageLabel` gained a `clicked` signal that fires on a simple
  left-click (no drag) **only in `MODE_NAV`**, so it never interferes with
  axis-point selection, ROI/template selection, or right-button panning.

### Code changes

- **`ZoomableImageLabel`**: added `clicked = Signal()`, a `_left_press_pos`
  tracker (set on left-press in `MODE_NAV`), and a release handler that emits
  `clicked` when the pointer barely moved (≤ 4 px).
- **`create_wand_tab_v2()`**: rebuilt the visualization area to the
  `QStackedWidget` (`Cams`) + `3D View` structure described above; removed the
  old per-camera `QFormLayout` (`vis_grid_layout`) and the 4 default rows.
- **`_update_wand_table()`**: the visualization rebuild now just calls
  `self._build_cam_vis_grid(count)` instead of clearing/recreating per-camera
  tabs.
- **New methods**:
  - `_build_cam_vis_grid(count)` — (re)creates the camera labels and lays them
    out 2 per row; wires each label's `axis_point_selected` and `clicked`.
  - `_on_cam_label_clicked(cam_idx)` — toggles expand/collapse.
  - `_collapse_cam_view()` — returns the expanded camera to the grid (also the
    "← Back to grid" button handler).
  - `_show_cam_in_vis(cam_idx, expand=False)` — switches to the "Cams" tab and
    optionally expands a camera; replaces the old
    `vis_tabs.setCurrentIndex(cam_idx)` focus calls in `_focus_axis_camera`
    (expand) and the detection-display path (grid).

### Notes / guarantees

- **No algorithm changes.** Only the layout/interaction of the image preview
  area changed. All image display, point overlays, axis selection, zoom and pan
  continue to use the same `self.cam_vis_labels[cam_idx]` `ZoomableImageLabel`
  objects as before.
- Verified headless (`QT_QPA_PLATFORM=offscreen`, `OpenLPT` conda env): tabs
  resolve to `Cams` / `3D View`; 4 cams produce a 2×2 grid and 6 cams a 3×2
  scrollable grid; expand reparents the label and collapse restores its grid
  slot.

---

## 3. Editable numeric input for "Sensitivity" (Point Detection)

**Date:** 2026-06-12
**File:** `modules/camera_calibration/widgets.py`

### What it does

The **Sensitivity** control on the Point Detection page previously had only a
drag slider with a read-only value label. That read-only label is replaced with
an **editable `QDoubleSpinBox`**, so the value can be typed (or stepped) exactly
as well as dragged. The slider and the input are **two-way synced**: dragging the
handle updates the number, and typing/stepping the number moves the handle.

### How it works

`SimpleSlider` (the widget used for Sensitivity) now holds a `QDoubleSpinBox`
configured from its `min_val` / `max_val` / `decimals` (range `0.5–1.0`, step
`0.01`, 2 decimals for Sensitivity). Sync is guarded against feedback loops:

- `setValue()` and the slider drag update the spinbox via `_set_spin_silently()`
  (which blocks the spinbox's `valueChanged` while setting it).
- `_on_spin_changed()` (connected to the spinbox) updates the slider value and
  repaints the handle, then re-emits `SimpleSlider.valueChanged`.

Because all detection code reads the value through `sensitivity_slider.value()`
and the public `value()` / `setValue()` API is unchanged, no call sites needed
updating.

### Notes / guarantees

- **No algorithm changes.** Only the Sensitivity widget gained a typed input;
  the value it produces is identical.
- `SimpleSlider` is used only for Sensitivity, so this change is scoped to that
  control (the radius `RangeSlider` is a separate widget and is untouched).
- Verified headless (`QT_QPA_PLATFORM=offscreen`, `OpenLPT` conda env): slider →
  spinbox and spinbox → slider stay in sync with a single `valueChanged` emit per
  change; range/step/decimals are `0.5–1.0` / `0.01` / `2`.

---

## 4. "Generate CLI" — terminal command equivalent to "Process All Frames"

**Date:** 2026-06-12
**Files:**
- `modules/camera_calibration/wand_calibration/point_detection_cli.py` (new)
- `modules/camera_calibration/view.py`

### What it does

Adds a **"Generate CLI"** button on the Point Detection page (Wand Calibration).
Pressing it resolves the **T0** folder (captured by "Auto-Load Cameras from Root
(T0)", or the common parent of the loaded camera folders) and writes a
**single-line** command into **`T0/Point_Detection_CLI.txt`**.

Copy that line into a terminal and it runs **exactly what the
"Process All Frames / Resume" button does** — the same detection
(`WandCalibrator.detect_wand_points_generator`) over all frames in `T0/cam<N>/`,
with the detection settings currently set in the UI (wand type, radius range,
sensitivity, detect mode) — and writes the same CSV (`T0/wand_points.csv`). The
only difference is it runs headless, without the GUI.

Example line written to `Point_Detection_CLI.txt`::

    "<python>" "<repo>/modules/camera_calibration/wand_calibration/point_detection_cli.py" \
        --t0 "<T0>" --wand-type dark --min-radius 20 --max-radius 200 \
        --sensitivity 0.850 --detect-mode fast --output "<T0>/wand_points.csv"

### How it matches "Process All Frames"

The CLI is a thin driver. `main()` discovers the `cam<N>` subfolders of `--t0`
(sorted ascending → camera slots 0..N-1, the same mapping the Root-folder loader
uses), builds the per-camera image dict (each folder's images, sorted), then
**consumes `detect_wand_points_generator(...)` to completion** — the very
generator the GUI's `WandDetectionWorker` runs for "Process All". That generator
does the parallel raw detection, per-camera radius stats, small/large filtering,
and autosaves the final CSV (Raw + Filtered) to `--output`. No detection logic is
duplicated or changed.

Because it is literally the same code path, the CLI output matches the GUI's
"Process All" output (subject to the same fast-mode RANSAC non-determinism the
GUI already has).

### Output CSV

Whatever `detect_wand_points_generator` / `export_wand_data` already produce:
header `Frame, Camera, Status, PointIdx, X, Y, Radius, Metric` with `Raw`,
`Filtered_Small`, and `Filtered_Large` rows.

### CLI flags

`--t0` (required), `--wand-type {dark,bright}`, `--min-radius`, `--max-radius`,
`--sensitivity`, `--detect-mode {fast,reliable}`, `--output`
(default `<t0>/wand_points.csv`), `--resume` (resume from an existing output CSV,
like the GUI's Resume). Runnable as `python -m ...` or as a loose script
(absolute-import fallback).

### Code changes

- **New module** `point_detection_cli.py`:
  - `discover_cam_folders`, `list_cam_images`, `build_image_paths_dict` — mirror
    how the GUI loads cameras from T0.
  - `run_process_all(...)` — instantiates `WandCalibrator` and drives
    `detect_wand_points_generator` to completion.
  - `build_cli_command(...)` — renders the one-line command.
  - `main(argv)` — argparse entry point.
- **`view.py`**:
  - New **"Generate CLI"** button on the Point Detection page.
  - `_generate_point_detection_cli()` resolves T0, reads the UI settings, and
    writes the one-line command (it does *not* run detection — that is the
    terminal command's job).
  - Helper `_wand_cam_folders`.
  - `_load_wand_root_folder` stores `self.wand_root_dir` / `self.wand_t0_dir` so
    this feature knows where T0 is.

### Notes / guarantees

- **No detection-algorithm changes.** The CLI re-uses
  `detect_wand_points_generator` and `WandCalibrator` unchanged; it only drives
  them from the command line instead of from the GUI worker.
- Verified (`OpenLPT` conda env): the button writes exactly **one line**
  reflecting the UI settings; running that line as a subprocess from an unrelated
  directory completes (returncode 0, "Valid Frames: 60/60") and produces a
  `wand_points.csv` with the expected `Raw` / `Filtered_Small` / `Filtered_Large`
  rows — identical structure to the GUI "Process All" export.
---

## 5. "Config Load" — import / export the Calibration-page settings

**Date:** 2026-06-12
**File:** `modules/camera_calibration/view.py`

### What it does

Adds a **"Config Load"** section at the top of the **Calibration** sub-tab of the
Wand Calibration page, with two buttons:

- **Export Config** — saves all current Calibration-page settings to a JSON file.
- **Import Config** — loads those settings back from a JSON file.

### Settings covered

- Camera Model (`wand_model_combo`), Wand Length (`wand_len_spin`), Distortion
  params (`dist_model_combo`).
- Refraction: Number of Windows (`window_count_spin`), per-camera Camera→Window
  mapping (the combo in each row of `cam_window_table`), and the three media
  segments (`media1/2/3` type + refractive index, plus window thickness).
- Error filters: "Delete when proj error >" and "Delete when wand len error >"
  (enabled state + threshold).

### Code changes

- New **"Config Load"** `QGroupBox` with **Import Config** / **Export Config**
  buttons added at the top of the Calibration tab in `create_wand_tab_v2()`.
- `_collect_cal_config()` → JSON-able dict of all settings above.
- `_apply_cal_config(cfg)` → applies a dict back to the widgets. Window count is
  set first (it rebuilds `cam_window_table`), then the per-camera window mapping
  is applied; combo indices are range-checked.
- `_export_cal_config()` / `_import_cal_config()` → file dialogs + JSON
  read/write with error handling.

### Notes / guarantees

- **No algorithm changes.** This only serialises/restores existing UI controls.
- Combo selections are stored as indices and clamped on import, so an out-of-range
  or partial config won't crash — missing keys keep the current value.
- Verified headless (`OpenLPT` conda env): a full round-trip
  (set values → export JSON → apply to a fresh view → re-collect) is an **exact
  match**, including the per-camera window map and all refraction/filter fields.

---

## 6. "Generate CLI" on the Calibration page + green button styling

**Date:** 2026-06-12
**Files:**
- `modules/camera_calibration/wand_calibration/wand_calibration_cli.py` (new)
- `modules/camera_calibration/view.py`

### Button styling (HZ_fix)

The Point Detection "Generate CLI" button (Change 4) and the new Calibration
"Generate CLI" button now use a **green** style matching the preprocessing page's
"Generate CLI" button (`background-color:#1f5f3a`, hover `#2d7a4d`). Defined once
as `self.GENERATE_CLI_BTN_STYLE` in `CameraCalibrationView.__init__`.

### Calibration "Generate CLI"

Adds a **"Generate CLI"** button directly **below "Run Calibration"** on the
Calibration sub-tab. Pressing it:

1. Reads the Calibration-page settings (wand length, distortion model, camera
   model) and the per-camera focal / image size from the detection table
   (`_collect_camera_settings_from_table`).
2. Prompts for the **wand-points CSV** produced by the detection step ("import
   the csv from previous step").
3. Writes a **single-line** command into `Calibration_CLI.txt` (next to the CSV).

Copy that line into a terminal and it runs the same thing the "Run Calibration"
button runs and writes the resulting `camFile/cam<N>.txt` parameter files. The
generated command **honors the UI camera model**:

- **Pinhole** — `WandCalibrator.calibrate_wand` + `export_to_file`.
- **Pinhole+Refraction** — `RefractiveWandCalibrator.calibrate` (the same
  pipeline `RefractiveCalibWorker` runs), which writes the cam files itself.

Example lines::

    # Pinhole
    python "<repo>/.../wand_calibration_cli.py" \
        --points "<wand_points.csv>" --wand-length 10.0 --distortion 0 \
        --camera-model pinhole --output "<out_dir>" \
        --cam "0,9000,1280,800" --cam "1,9000,1280,800"

    # Pinhole+Refraction
    python "<repo>/.../wand_calibration_cli.py" \
        --points "<wand_points.csv>" --wand-length 10.0 --distortion 0 \
        --camera-model refraction --output "<out_dir>" \
        --cam "0,9000,1280,800" --cam "1,9000,1280,800" \
        --num-windows 1 --cam-window "0:0" --cam-window "1:0" \
        --window-media "0:1.0,1.49,1.33,10.0"

### How it matches "Run Calibration"

`run_calibration()` dispatches on the model:

- **Pinhole** — `WandCalibrator()` → `load_wand_data_from_csv` → set
  `image_size` / `camera_settings` / `dist_coeff_num` (exactly as
  `_run_wand_calibration`) → `calibrate_wand` → `export_to_file`.
- **Refraction** — `run_refractive_calibration()` builds a base `WandCalibrator`
  from the CSV with the same attributes the GUI's `RefractiveCalibWorker` sets on
  its mock base (`wand_points`, `camera_settings`, `image_size`,
  `dist_coeff_num`, `wand_length`, `initial_focal`, `active_cam_ids`,
  `run_precalibration_check`) and calls
  `RefractiveWandCalibrator.calibrate(num_windows, cam_to_window, window_media,
  out_path, ...)`.

No calibration logic is duplicated or changed.

### CLI flags

`--points` (required), `--wand-length`, `--distortion {0,1,2}`,
`--camera-model {pinhole,refraction}`, `--cam id,focal,width,height` (repeat per
camera), `--init-focal`, `--output`. Refraction-only: `--num-windows`,
`--cam-window cam_id:window_id` (repeat), `--window-media wid:n1,n2,n3,thickness`
(repeat). Runnable as `python -m ...` or as a loose script.

### Notes / guarantees

- **No calibration-algorithm changes.** The CLI re-uses `WandCalibrator`,
  `calibrate_wand` / `export_to_file`, and `RefractiveWandCalibrator.calibrate`
  unchanged; the button passes the UI's refraction settings (windows, camera→
  window mapping, media indices/thickness) into the command.
- Verified end-to-end (`OpenLPT` conda env) on a synthetic two-camera wand
  `wand_points.csv`:
  - **Pinhole** — `RESULT: True`, reprojection RMS ≈ 0.001 px, writes
    `camFile/cam0.txt` + `cam1.txt`.
  - **Refraction** — `RESULT: True`, the refractive pipeline runs to completion
    and writes `camFile/cam0.txt` + `cam1.txt` with plane / media parameters.
  - The refraction command builds with the expected `--num-windows`,
    `--cam-window`, `--window-media` flags. Both "Generate CLI" buttons render
    with the green style.
- **Loose-script imports.** The refractive path's
  `from .refraction_wand_calibrator import ...` (and the top-level
  `WandCalibrator` import) fall back to absolute imports so the file runs both as
  `python -m ...` and as a plain `python <path>.py` script (the form the button
  writes).
---

## 7. Bug fixes / workflow tweaks (Wand Calibration page)

**Date:** 2026-06-12
**File:** `modules/camera_calibration/view.py`

Four UI/workflow fixes, all in `create_wand_tab_v2()` and its helpers. No
detection / calibration algorithms changed.

### 7a. "Auto-Load Cameras from Root (T0)" — validate frame counts

`_load_wand_root_folder()` now **validates before loading anything**:

- If a `cam<N>` folder contains **no images**, the load is **rejected** — an
  error dialog lists the empty folder(s) and **nothing is loaded** (no Num
  Cameras change, no table rebuild).
- If the **frame counts differ between cameras** (e.g. `cam0=120, cam1=119`),
  the load is **rejected** with a dialog showing the per-camera counts. All
  cameras must have the same number of frames.
- The existing "no `T0`" / "no `cam<N>` folders" errors are unchanged.

The image lists are gathered and checked **first**; UI state
(`wand_root_dir`/`wand_t0_dir`, Num Cameras, the camera table, `wand_images`) is
only mutated once validation passes — so a rejected load leaves the previous
state intact. The success dialog now also reports the per-camera frame count.

### 7b. "Output Path" section — no double prompt on "Process All Frames"

**Before:** clicking **Process All Frames** popped a file dialog for the save
path, and `_on_process_finished()` *always* asked again ("Detection complete. Do
you want to export the point data?") — a redundant second prompt for a file the
worker had already auto-saved.

**Now:** a new **"Output Path"** `QGroupBox` (a `QLineEdit` +
**Browse…** button, `_browse_wand_output_path()`) sits **above the three action
buttons** (Test Detect / Process All Frames / Generate CLI) on the Point
Detection tab.

- **Process All Frames** reads the autosave path from this field
  (`wand_output_path_edit`). If it is **empty**, a warning dialog asks the user
  to set it first and the run is aborted.
- The start-of-run info popup and the start-of-run "Select Save File" dialog were
  **removed** (the path now comes from the field). Resume detection (existing
  file → Resume/Overwrite question) is unchanged.
- The redundant end-of-run export prompt in `_on_process_finished()` was
  **removed** — results are auto-saved to the Output Path during processing. The
  partial-data "rescue" export on failure is unchanged.

### 7c. Calibration tab — split Import / Export Config

The Calibration sub-tab previously had a single "Config Load" box with **Import
Config** *and* **Export Config** at the top. Now:

- **Import Config** stays in the **"Config Load"** box at the **top** of the tab.
- **Export Config** is moved **down**, to sit directly **above "Load Wand Points
  (from CSV)"**. Same button, same `_export_cal_config()` handler.

### 7d. Calibration "Generate CLI" — reuse the already-loaded CSV

`_generate_calibration_cli()` previously always opened a file dialog for the
wand-points CSV. Now it **reuses the CSV already loaded** via **"Load Wand Points
(from CSV)"**: `_load_wand_points_for_calibration()` stores the path in
`self.loaded_wand_csv_path`, and Generate CLI uses it directly when it still
exists on disk. It only falls back to the file dialog when **no CSV has been
loaded** (or the remembered file is gone).

### Verification

Headless (`QT_QPA_PLATFORM=offscreen`, `OpenLPT` conda env): the view builds with
the new `wand_output_path_edit` / `btn_browse_output` widgets, `Import Config`
remains at the top, `Export Config` is present above Load Wand Points, and
`view.py` compiles clean (`py_compile`).

---

## 8. Image Preprocessing CLI — fixed camera-ID convention and output naming

**Date:** 2026-06-13
**Files:**
- `modules/image_preprocessing/cli.py`
- `modules/image_preprocessing/runner.py`
- `modules/image_preprocessing/view.py`
- `tests/test_image_preprocessing_cli.py`, `tests/test_image_preprocessing_io.py`

### Problem

The `openlpt preprocess` CLI used **1-based** camera indices everywhere
(`enumerate(..., start=1)`), so `--input-root` with `cam0/cam1/cam2/cam3`
subfolders produced output folders `cam1/cam2/cam3/cam4` — off by one from
both the input folder names and the 0-based camera IDs used by Wand
Calibration (`cam0.txt`..`cam3.txt`) and the Tracking page (`cam0`..`cam3`).

The CLI also wrote per-camera image lists as `cam<N>_image_list.txt`, but
`gui/views/tracking_settings_view.py` and `gui/views/tracking_view.py` only
ever look for `cam<N>ImageNames.txt` (this is what `config.txt`'s "# Image
File Path" section references, and what the GUI's own
`_write_image_name_files()` in `modules/image_preprocessing/view.py` writes).
So a CLI-produced dataset could not be picked up by Tracking without a manual
rename.

### Fix

- **`runner.py`**: `image_list_path = output_dir / f"cam{cam_idx}_image_list.txt"`
  → `f"cam{cam_idx}ImageNames.txt"`. This is the only place the filename is
  decided; `cli.py`'s summary printout (`_print_summary`) needed no change.
- **`cli.py`**: every `enumerate(..., start=1)` that assigns a camera index
  (`--input-root`, `--input-list`, `--image`, `--cine`, and the matching
  `_build_backgrounds` branches) is now `enumerate(..., start=0)`.
  `--camera-index` is now validated as `>= 0` (was `>= 1`) and documented as
  0-based. Help text/epilog examples updated to `cam0`/`cam1` (was
  `cam1`/`cam2`).
- **`view.py`** (`_build_preprocess_cli_command`, the GUI's "Generate CLI"
  button for Preprocessing): removed the `cam_idx + 1` translation that had
  been compensating for the CLI's old 1-based convention (and the
  accompanying note about "GUI camera tabs are zero-based; the CLI maps them
  to one-based..."). The generated `--camera-index` and `--input-list
  /path/to/cam<N>ImageNames.txt` placeholders now use the same `cam_idx` as
  the GUI's own camera tabs.
- **Tests**: `cam1_image_list.txt` → `cam1ImageNames.txt` (filename-only
  changes, where `--camera-index 1` was explicitly passed so `cam1` itself is
  correct); the `--input-root` auto-detection test now expects 0-based
  `cam_idx` values `[0, 0, 1, 1]` (was `[1, 1, 2, 2]`) and
  `cam0ImageNames.txt`/`cam1ImageNames.txt`.

### Net effect

`python -m modules.image_preprocessing.cli --input-root <root>` where `<root>`
contains `cam0/`, `cam1/`, `cam2/`, `cam3/` now produces:

```
<root>/imgFile/
├── cam0/...            cam0ImageNames.txt
├── cam1/...            cam1ImageNames.txt
├── cam2/...            cam2ImageNames.txt
└── cam3/...            cam3ImageNames.txt
```

— matching folder names, image-list filenames, and camera IDs throughout
Preprocessing → Tracking → Calibration, regardless of input order, with no
renaming step.

### Verification

`pytest tests/test_image_preprocessing_cli.py tests/test_image_preprocessing_core.py
tests/test_image_preprocessing_io.py` → 21 passed. Also ran the CLI end-to-end
on a synthetic `cam0..cam3` root: output folders and `cam<N>ImageNames.txt`
files are 0-based and match the input folder names exactly.

---

## 9. `cli_tracking_settings.py` — headless "Save Configuration" for the Settings page

**Date:** 2026-06-13
**File:** `cli_tracking_settings.py` (new, repo root)

### What it does

Writes `config.txt` + `bubbleConfig.txt`/`tracerConfig.txt` into a project
directory — the same two files produced by clicking **"Save Configuration"**
on the Tracking **Settings** page — without opening the GUI. Intended for
SLURM/cluster pipelines: run it once (or every time) before the tracking
binary, so settings don't need to be re-entered in the GUI per job.

Defaults match the most common bubble-tracking setup, per request:

```
--fps 3000  --object-type bubble
```

### How it matches "Save Configuration"

This is a thin driver, **not a reimplementation**. It headlessly instantiates
the real `TrackingSettingsView` (`gui/views/tracking_settings_view.py`) under
`QT_QPA_PLATFORM=offscreen`, sets `project_path` and calls the same
`_update_paths()` the GUI calls — which auto-derives Number of Cameras (from
`imgFile/` subfolder count), Frame End (from image count in the first camera
folder), Image/Camera/Output paths, the View Volume and Voxel-to-mm (adaptive
estimation from `camFile/cam<N>.txt`), and the IPR 2D/3D tolerances (from
camera reprojection/triangulation error stats) — then applies any CLI
overrides on top, and calls `_save_configuration()` directly. The written
files are therefore identical to what the GUI would write for the same field
values.

`QMessageBox.warning/information/critical` are monkeypatched to no-ops so the
headless run doesn't block on a dialog; status normally shown in a message box
(e.g. "Camera Parameters Missing") is instead summarized on stdout.

### Flags

`project_dir` (positional) plus optional overrides for everything on the
Settings page: `--object-type {bubble,tracer}`, `--fps`, `--n-cameras`,
`--frame-start`, `--frame-end`, `--n-threads`, `--image-path`,
`--camera-path`, `--output-path`, `--volume XMIN XMAX YMIN YMAX ZMIN ZMAX`,
`--voxel-to-mm`, `--resume` / `--resume-frame`, IPR/Shake/STB/predictive-field
overrides (`--ipr-2d-tol`, `--ipr-3d-tol`, `--ipr-loops`, `--ipr-reduce-cam`,
`--ipr-reduced-loops`, `--shake-width`, `--shake-loops`,
`--shake-ghost-thresh`, `--stb-initial-radius`, `--stb-initial-frames`,
`--stb-avg-spacing`, `--pred-grid X Y Z`, `--pred-search-radius`), tracer-only
(`--tracer-int-thresh`, `--tracer-radius`), and bubble-only
(`--bubble-min-radius`, `--bubble-max-radius`, `--bubble-sensitivity`).
`--dry-run` prints the resolved settings without writing any files.

Overrides are applied **after** auto-detection, so an explicit flag always
wins over the auto-derived value.

### `--n-threads 0` ("use all available")

`config.txt`'s "Number of Threads" field documents `0` as "use as many as
possible" (`inc/libSTB/Config.h: _n_thread = 0`), but the GUI's
`n_threads_spin` has range `1..128` and cannot represent `0`. When
`--n-threads 0` is passed, the CLI writes the rest of `config.txt` via
`_save_configuration()` as usual, then patches the "Number of Threads" line to
`0` directly. Any other `--n-threads N` value is written normally via the
spinbox.

### Notes / guarantees

- **No tracking-algorithm changes.** This only drives the existing Settings
  widget through its existing setters and calls its existing save method.
- Verified headless (`QT_QPA_PLATFORM=offscreen`):
  - Defaults (`--fps 3000 --object-type bubble`, no other flags) on a 2-camera
    project produce a `config.txt`/`bubbleConfig.txt` pair byte-identical in
    structure to the GUI's output for the same field values.
  - `--object-type tracer` writes `tracerConfig.txt` with the tracer-specific
    Object Info block (`tracer_int_thresh`, `tracer_radius`).
  - On a 4-camera project with real `camFile/cam0..3.txt` calibration outputs,
    Number of Cameras, Frame End, View Volume, Voxel-to-mm, and IPR 2D/3D
    tolerances are all auto-derived exactly as `_update_paths()` /
    `_on_cam_path_changed()` would compute them in the GUI.
  - `--n-threads 0` and `--n-threads 24` both round-trip correctly into
    `config.txt`.
  - `--dry-run` prints the resolved configuration and writes nothing.

### Example SLURM usage

```bash
#!/bin/bash
#SBATCH --job-name=openlpt_settings
#SBATCH --cpus-per-task=24
module load anaconda  # or your python env
python cli_tracking_settings.py "$PROJECT_DIR" \
    --frame-start 0 --frame-end 49931 \
    --bubble-min-radius 4 --bubble-max-radius 60 --bubble-sensitivity 0.8 \
    --n-threads "$SLURM_CPUS_PER_TASK"
```

---

## 10. "Generate CLI" button on the Settings page

**Date:** 2026-06-15
**File:** `gui/views/tracking_settings_view.py`

### What it does

Adds a **"Generate CLI"** button (green, matching the Preprocessing / Wand
Calibration "Generate CLI" buttons) to the Actions panel, directly below
**"Save Configuration"**. Pressing it opens a dialog showing the
`cli_tracking_settings.py` command (see section 9) that reproduces
**"Save Configuration" with the CURRENT field values** - copy that line into
a terminal/SLURM script to write `config.txt` +
`bubbleConfig.txt`/`tracerConfig.txt` headlessly, without opening the GUI.

### How it matches "Save Configuration"

`_build_settings_cli_command()` reads every field `_save_configuration()`
reads (object type, FPS, camera/frame/thread counts, image/camera/output
paths, view volume, voxel-to-mm, resume flag/frame, IPR/shake/STB/predictive-
field parameters, and tracer- or bubble-specific parameters) and maps each one
to the matching `cli_tracking_settings.py` flag, so the generated command is
self-contained: it does not rely on `cli_tracking_settings.py`'s own
auto-detection to reproduce the values currently shown in the UI. The dialog
notes that flags can be removed if the user wants a value re-derived from
`imgFile`/`camFile` on the run instead.

### Verified

Headless (`QT_QPA_PLATFORM=offscreen`): for both Bubble and Tracer object
types, running the generated command produces `config.txt` +
`bubbleConfig.txt`/`tracerConfig.txt` **byte-identical** to calling
`_save_configuration()` directly with the same field values.

### Relationship to the bubble-reference-image fix (item... see C++ changes)

No interaction. This CLI only writes `config.txt`/`[type]Config.txt`; the
bubble reference image is built at tracking runtime (C++ `STB`/`IPR`), after
these config files are read. Neither this button nor
`cli_tracking_settings.py` needed any changes for that fix.

---

## 11. "Validate Settings" — bubble-reference-image-aware, responsive, frame-scanning

**Date:** 2026-06-15
**File:** `gui/views/tracking_settings_view.py`

**Scope note:** this is a Python/GUI-only change to the "Validate Settings"
button. The tracking binary is **unmodified** - `src/srcSTB/IPR.cpp`,
`src/srcSTB/STB.cpp`, `inc/libSTB/STB.h`, `src/main.cpp`, and
`src/pybind_OpenLPT/pySTB.cpp` are at their original upstream state (original
`THROW_FATAL_CTX` on `calBubbleRefImg` failure, only ever checks
`frame_start`). "Validate Settings" is a setup-time helper: it scans
`frame_start..frame_end` for a frame whose 2D detections + 3D matching would
pass `calBubbleRefImg`'s actual 3 gates (same function, called via the
existing pybind `BubbleRefImg.calBubbleRefImg` binding), and - if that frame
needed relaxed IPR 2D/3D tolerances - updates the '2D tolerance'/'3D
tolerance' widgets so "Save Configuration" writes those into
`bubbleConfig.txt`. `config.txt`'s Frame Start/Frame End are always exactly
what the user typed and are never changed by Validate or by this.

### Problems fixed (3 issues from testing)

1. **UI froze / Cancel unresponsive on long scans.** A real dataset can need
   150+ frames scanned before finding one with enough bubbles, each with up to
   ~16 tolerance-bump retries - thousands of blocking `StereoMatch().match()`
   calls with `wasCanceled()` only checked once per frame. The
   `QProgressDialog(0,0)` busy-bar was also not useful (no determinate
   progress to show).
2. **Frame range came from `config.txt`, not the UI.** Validate required
   `config.txt` to exist (it's the only source of camera params/image paths),
   but read `frame_start`/`frame_end` from it too - so if the user changed
   "Frame Start"/"Frame End" in the UI without re-saving, Validate silently
   scanned the OLD range.
3. **Pass criterion (`count_3d >= avg_2d_count/4`) didn't match
   `calBubbleRefImg`'s real gates**, so Validate could report success on a
   frame where the actual bubble-reference-image build would still fail (3
   independent fixed-count gates, all requiring >5 qualifying bubbles: every
   selected 3D bubble must have radius>6px in EVERY camera; an intensity-peak
   filter (`max_peak > 0.8*mean_peak`); and per-pixel coverage across the
   reference-image template). A frame with "6 3D objects" can still fail all
   three.

### Fix

- **New `_ValidationStatusDialog`** (small `QDialog` + `QLabel` + "Stop"
  button) replaces `QProgressDialog`. `wasCanceled()`/`setLabelText()` have
  the same call signatures the validation code already used, so the rest of
  the flow needed minimal changes. `QApplication.processEvents()` is now
  called and `wasCanceled()` checked at every step inside both the 2D- and
  3D-tolerance retry loops (not just once per frame), so clicking "Stop" takes
  effect within a fraction of a second, even mid-frame. A canceled run reports
  "Validation stopped at frame N (scanned start..N)" instead of a
  pass/fail verdict.
- **Frame range from the UI**: `frame_start`/`frame_end`/object type are read
  from `self.frame_start_spin`/`self.frame_end_spin`/`self.obj_type_combo`
  (current UI values), not from `basic_settings._frame_start`/`_frame_end`.
  `config.txt` is still required (camera models / image paths / object config
  path come from there), but if its saved Frame Range differs from the UI,
  a note says so and suggests "Save Configuration".
- **3-gate `calBubbleRefImg` pass criterion** (Bubble only): after each
  `StereoMatch().match()` (initial and each tolerance-bump retry), if
  `count_3d > 5`, `_run_validation_on_frame` calls
  `lpt.BubbleRefImg().calBubbleRefImg(obj3d_list, obj2d_list, camera_models,
  image_list, "", 6.0, 5)` (empty `output_folder` -> no files written;
  `calBubbleRefImg` raises `RuntimeError` on failure, caught and treated as
  "not yet"). The frame is reported as passed only if this succeeds. Tracer
  has no reference-image concept, so it keeps the old proportional
  `count_3d >= avg_2d_count/4` proxy.
- **Scan stops at the first passing frame**; frames with zero 2D detections in
  any camera are skipped (per-frame data issue, scan continues). On full
  exhaustion, reports "check `camFile/cam*.txt`" as before.
- **Tolerance widgets ARE updated on success, `config.txt` Frame Range is
  NOT**: if the passing frame needed `tol_2d_px`/`tol_3d_mm` increased beyond
  the config's current values, `ipr_2d_tol`/`ipr_3d_tol` are set to those
  values (independently - only the tolerance that actually changed is
  touched). The success message tells the user to click "Save Configuration"
  to write these into `bubbleConfig.txt`. `frame_start_spin`/`frame_end_spin`
  (and therefore `config.txt`'s Frame Range) are never modified by Validate.
  `config.txt` itself is still not written by Validate.

### "Validate first, Save once" — no config.txt required beforehand

Initially "Validate Settings" required `config.txt` to already exist (it's
the only source of camera params/image paths for
`lpt.BasicSetting.readConfig()`), forcing: Save -> Validate (updates
tolerance widgets) -> Save again. This is backwards from the intended
workflow (Validate first to find a frame, THEN Save once with that result).

Fixed by extracting `_save_configuration()`'s file-content generation into
`_render_config_files(project_dir, path_mode)`:
- `path_mode="relative"` (used by `_save_configuration()`, unchanged output):
  camFile/imgFile/output paths relative to `project_dir`, as before.
- `path_mode="absolute"` (new, used only by Validate): the SAME content but
  with camFile/imgFile/output paths as absolute paths into the real project
  directory - so a `config.txt` written anywhere can still find the real
  project's data (`BasicSetting::readConfig` resolves relative paths against
  the directory `config.txt` lives in, via `_config_root`).

`_validate_settings()` now: renders config.txt + `[type]Config.txt` from
CURRENT UI values (`path_mode="absolute"`), writes them to a fresh
`tempfile.mkdtemp()` directory, calls `BasicSetting.readConfig()` on the temp
`config.txt`, runs the frame scan, then `shutil.rmtree()`s the temp directory
in a `finally` block (even on exceptions). The real project's
`config.txt`/`bubbleConfig.txt` are **never read or written** by Validate -
only by "Save Configuration".

### Block search instead of one-by-one scan (HZ_fix, 2026-06-15)

`_validate_settings`'s frame loop no longer validates `frame_start..frame_end`
one frame at a time. It now drives a **complete coarse-to-fine** block search
from `modules/image_preprocessing/reference_frame.py`:
`find_reference_frame_blocks(..., block_size=fps//5, tau=6)`. It cheap-probes
frames at progressively finer strides (`fps/5`, `fps/25`, … down to every frame)
with the **`count_3d` proxy** (`make_stereomatch_count3d_proxy`, a single
`StereoMatch` at the validator's MAX retry tolerances `tol_2d+5` / `tol_3d+1mm`,
so a frame is pruned only if NO validation attempt could pass), and runs the
**unchanged** `_run_validation_on_frame` on the first frame that clears the gate.

**Completeness:** if every block head triangulates nothing, it does **not** fail
— it shrinks the block and probes the in-between frames, only reporting "no valid
frame" once **every** frame has been cheap-probed. A valid frame at a coarse
position is still found fast (early levels); the full sweep happens only when
failing. Each frame is probed at most once. The expensive validator is still
gated by `count_3d >= tau` (zero calls when nothing triangulates). Cancellation
is checked during the cheap probes; tolerance-update + success/failure dialogs
preserved; when nothing triangulates, one real validation runs on the
bubble-richest probe for the diagnostic and the failure dialog says all frames
were checked.

`_run_validation_on_frame` / `calBubbleRefImg` are **not modified** — only the
scan that drives them. On the real 4-camera / 49,932-frame T1 dataset (camFile
triangulates nothing) it cheap-probes coarse-to-fine and reports "no valid
frame -> check calibration" with **0 expensive validations** (the full cheap
sweep is `O(n)`, same order as the original one-by-one scan but without the
retry ladder, and Stop-cancellable).

### Verified

Headless (`QT_QPA_PLATFORM=offscreen`, mocked `pyopenlpt` incl. `BubbleRefImg`):
- Frames 0-2 fail (4 matched, `calBubbleRefImg` raises), frame 3 passes at the
  config's original tolerances: scan stops at frame 3, reports "Validated
  Frame: 3", `ipr_2d_tol`/`ipr_3d_tol` unchanged, `config.txt` mtime unchanged.
- Same, but frame 3 only passes after `tol_2d_px` is bumped from 2.0px to
  3.5px: `ipr_2d_tol` is updated to 3.5, `ipr_3d_tol` stays at its original
  value (only the tolerance that actually changed is touched).
- All frames in `[0,3]` fail: reports the "needs >5 well-resolved bubbles ...
  check calibration" message after scanning the full range.
- Clicking "Stop" mid-frame (during the first frame's retry ladder) reports
  "Validation stopped at frame 0 (scanned 0..0)" almost immediately.
- **No `config.txt` exists at all** (fresh project, never saved): "Validate
  Settings" with Frame Start=1000/Frame End=10000 runs successfully (frame
  1000 itself passes after a 2D tolerance bump to 3.5px), updates
  `ipr_2d_tol`, and leaves no `config.txt`/`bubbleConfig.txt`/temp directories
  behind. Clicking "Save Configuration" afterward writes `config.txt` with
  `1000,10000` and `bubbleConfig.txt` with `2D tolerance [px] = 3.5`.
- Same, but the passing frame is 1003 (not `frame_start`=1000): scan reports
  "Validated Frame: 1003" with the frame_start-unchanged note, updates
  `ipr_2d_tol` to 3.5; "Save Configuration" still writes `config.txt`'s Frame
  Range as `1000,10000`.
- `_render_config_files(..., path_mode="relative")` output (used by "Save
  Configuration") is unchanged in format from before this refactor.


---

## 12. Block-based coarse-to-fine search for a valid bubble reference frame

**Date:** 2026-06-15
**Files:**
- `modules/image_preprocessing/reference_frame.py` (new)
- `modules/image_preprocessing/cli.py` (`find_reference_frame_from_detected`)
- `tests/test_reference_frame_search.py` (new)

### Problem

A bubble *reference frame* must (a) contain enough bubbles and (b) pass the
*existing* validation algorithm (e.g. the `calBubbleRefImg` 3-gate check used by
"Validate Settings", Change 11). The naive search validates frames 0, 1, 2, …
until one passes, and that validator is **expensive** (per-camera 2D detection +
cross-camera stereo matching + the reference-image gates). On real datasets a
valid frame can be 100+ frames in, so the naive scan runs the expensive validator
hundreds of times.

**The validation algorithm is not changed** — it is injected as a callable
(`is_valid(frame_index) -> bool`) and only ever *confirms* a candidate.

### Algorithm (coarse-to-fine, exploits temporal clustering of bubbles)

`find_reference_frame(n, *, is_valid, cheap_count, stride, tau, …)`:

- **L0 coarse probe** — sample frames at a coarse `stride` with a CHEAP proxy
  (`cheap_count`, a *sound necessary-condition* bubble count = min across cameras
  of the 2D blob count). `O(N/stride)` cheap reads.
- **L1 adaptive refine** — around each promising probe (proxy `>= tau`), densify
  the cheap proxy over the block (`±(stride-1)`) to find the bubble-richest frame
  and catch a window straddling a probe.
- **L2 confirm** — run the EXPENSIVE `is_valid` on candidates **best-first** and
  return the first that passes. ~`O(1)` validations in the common clustered case.
- **fallback** — a dense (stride-1) cheap pass validates every `>= tau` frame
  best-first, guaranteeing completeness over the above-threshold set.

If no `cheap_count` is supplied it degrades to jump-search + full-scan fallback
(early-exit win only).

### Complexity

- **Naive:** up to `N` *expensive* validations.
- **This:** `O(N/stride)` cheap reads + `O(block)` refine, and **~`O(1)`
  expensive validations** when valid frames cluster (worst case: number of frames
  above `tau`). With no proxy and `stride = √N` it is classic jump search
  (`O(√N)` probes) over contiguous validity.

### Correctness

- **Soundness is free:** a frame is returned only after `is_valid` confirms it —
  blocks/proxy only change which frames are tried and in what order.
- **Completeness** needs (i) the proxy to be a sound necessary condition
  (`is_valid(r)` ⟹ `cheap_count(r) >= tau`; tune the proxy so it never
  *under*-counts bubbles on a valid frame), and (ii) coverage of the valid window.

### Avoiding missed very short bubble windows

A probe `stride` only **guarantees** catching bubble windows *longer than*
`stride`; a window of length `<= stride` can fall between probes. Mitigations,
in order of preference:

1. **Set `stride <= shortest window you must catch`** — derive it from bubble
   persistence × fps (the conceptual block size is `2*stride-1`).
2. **Mandatory expand-on-hit refine (L1)** rescues windows straddling a probe and
   finds the richest frame.
3. **Dense cheap fallback** (default on): if the coarse/refine phase finds
   nothing, a stride-1 cheap pass guarantees no above-`tau` window is missed —
   `O(N)` *cheap* reads but the *expensive* validations stay minimal.
4. If single-frame windows must be caught and the minimum persistence is unknown,
   you cannot beat `O(N)` *cheap* reads in the worst case (a length-1 window can
   hide anywhere) — but you can still keep the *expensive* validations sub-linear,
   which is the real cost. `exhaustive_fallback=False` trades that completeness
   for strictly sub-linear behavior.

### Integration

`find_reference_frame_from_detected(detected, is_valid, *, frames=None,
stride=10, tau=6.0, …)` in `cli.py` builds per-camera frame readers
(`build_frame_readers`, TIFF or CINE, index-aligned) and the default cheap proxy
(`make_bubble_count_proxy`: threshold → `connectedComponentsWithStats` → count in
an area range → min across cameras), then runs the core search over the frames
`_build_tasks_from_input_root` enumerates. The caller supplies its own
`is_valid` (e.g. wrapping `calBubbleRefImg`).

### Verification

- `tests/test_reference_frame_search.py` (pure-Python, synthetic
  `cheap_count`/`is_valid`) — 6/6 pass: finds a valid frame with `<= 5`
  validations where naive needs ~600; returns `None` (0 validations) when none
  valid; short windows caught when `stride <= window`; a 1-frame window recovered
  by the dense fallback (and correctly missed with `exhaustive_fallback=False`,
  documenting the trade-off); no-proxy jump-search path works.
- End-to-end (cv2, synthetic 2-camera TIFFs, bubbles only in frames 40–45):
  `find_reference_frame_from_detected` returns frame 45 with **1** expensive
  validation and 22 cheap reads of 60 frames, no fallback.
- Integration-tested against the **real** `calBubbleRefImg` validator (the GUI's
  unmodified `_run_validation_on_frame`) on a real 4-camera / 49,932-frame
  dataset: the search drives the real pipeline end-to-end and, when the dataset's
  calibration triangulates nothing (0 3D matches on every probed frame), returns
  `None` after a bounded 120 validations in ~65 s instead of scanning all 49,932
  frames — i.e. the “no valid frame” path degrades gracefully. (A speed benchmark
  needs a dataset whose calibration actually triangulates.)
- Added optional `refine_radius` to decouple the L1 refine cost from the coarse
  miss-guarantee `stride` (defaults to `stride`).
- **Complete coarse-to-fine (final design).** `find_reference_frame_blocks` was
  reworked to a multi-resolution sweep: probe at strides `block_size`,
  `block_size/subdiv`, … down to `min_block` (default 1 = every frame), each frame
  probed at most once, validating (gated by `count_3d >= tau`) the first frame
  that clears the gate. **It does not fail from block heads alone** — if the coarse
  heads triangulate nothing it shrinks the block and probes the in-between frames,
  reporting "no valid frame" only after *all* frames are cheap-probed. A valid
  frame at a coarse position is found fast; the full `O(n)` cheap sweep happens
  only when failing (same order as the original frame-by-frame scan, minus the
  retry ladder). The expensive validator stays gated (0 calls when nothing
  triangulates). `min_block > 1` bounds the sweep to `~n/min_block` cheap probes if
  a sub-complete scan is wanted. Tests: `count_3d=0` everywhere → probes every
  frame, 0 validations, then `None`; an interior-only valid frame is found by
  shrinking; `min_block=block_size` → exactly `n/block_size` probes.
- **Best design (hierarchical block + `count_3d` gate), benchmarked on real T1**
  (4 cams, 49,932 frames; `_run_validation_on_frame` reused **unchanged** as the
  confirm; new `make_stereomatch_count3d_proxy` as the cheap probe):
  - `find_reference_frame_blocks` with `block_size = fps/5 = 600`, `tau = 6`
    covered the full range in **84 cheap probes, 0 expensive validations**, 42 s,
    returning `None` — vs the earlier naive-per-block scan's **250 full
    validations / 135 s**. The `count_3d` gate means the expensive validator is
    never wasted (T1 triangulates nothing: `max count_3d = 0`).
  - Honest caveat: on T1 the cheap probe and the full validation are **both
    ~521 ms** — T1 is *2D-detection-bound* (`findObject2D` dominates; the match
    ladder is cheap on 0-match frames), so the ladder-skipping ~10x win only
    materializes on data that actually triangulates. Multi-threading is the
    weakest lever here: `findObject2D`/`StereoMatch.match` hold the GIL and the
    C++ is already internally OpenMP, so Python threads oversubscribe the cores.

---

## 13. "Error Matrix" popup on the Calibration page (Error Analysis)

**Date:** 2026-06-15
**File:** `modules/camera_calibration/view.py`

### What it does

Adds an **"Error Matrix"** button to the **Error Analysis** header row (right of
the "Error Analysis:" label, in `create_wand_tab_v2()`). It opens a dialog with
two parts:

- **Top — per-camera error stats** (projection error, px): a table with one row
  per camera plus an **"All cams"** row, columns **Camera, N, Mean, Median,
  Tail p%, Max**. A **"Tail %"** spin box (default 5%) lets the user set the
  percentile live — `Tail p%` is the projection error exceeded by the worst `p%`
  of frames (i.e. the `(100 - p)`th percentile, `np.percentile(vals, 100 - p)`).
  A line below shows the **wand-length error** summary (mean / median / tail p% /
  max, in mm), recomputed with the same `p`.
- **Bottom — the full error matrix**: a sortable, read-only table of
  `Frame x Cam<N>` projection errors plus `Len Err (mm)`, with cells exceeding
  the page's proj/len filter thresholds highlighted (same as the inline table).

### How it works

`_show_error_matrix()` reads the existing
`self.wand_calibrator.calculate_per_frame_errors()` (`{frame: {'cam_errors':
{cam: px}, 'len_error': mm}}`) — the same source the inline error table uses —
collects each camera's projection-error distribution, and computes Mean / Median
/ Tail-percentile / Max with numpy. Changing the Tail % spin box re-fills only the
stats table (the matrix is unchanged). If no calibration has been run yet, it
shows an info dialog instead.

### Notes / guarantees

- **No algorithm changes.** It only summarizes/visualizes the already-computed
  per-frame errors; nothing is recalculated or filtered.
- Verified headless (`QT_QPA_PLATFORM=offscreen`, synthetic 2-camera per-frame
  errors): the dialog builds with the per-camera + "All cams" rows, Mean/Median/
  Tail/Max populate correctly, the matrix has `Frame, Cam 1, Cam 2, Len Err (mm)`
  columns over all frames, the wand-length summary line renders, and changing
  Tail % updates the header and recomputes the tail values (10% -> lower, 1% ->
  higher), as expected for a percentile. `view.py` compiles clean.

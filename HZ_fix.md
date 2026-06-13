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

"""
HZ_fix: Block-based coarse-to-fine search for a valid bubble *reference frame*.

A reference frame must (a) contain enough bubbles and (b) pass an existing,
*unmodified* validation algorithm (e.g. the ``calBubbleRefImg`` 3-gate check used
by "Validate Settings"). The naive approach validates frames 0, 1, 2, … until one
passes — and the validation is expensive (per-camera 2D detection + cross-camera
stereo matching + the reference-image gates). On real datasets a valid frame can
be 100+ frames in, so the naive scan runs the expensive validator hundreds of
times.

This module finds a valid frame while calling the expensive validator as few
times as possible, exploiting the fact that bubbles are *temporally clustered*
(valid frames come in runs / "bubble windows"):

  L0  coarse probe   — sample frames at a coarse ``stride`` with a CHEAP proxy
                       (a sound necessary-condition bubble count). O(N/stride).
  L1  adaptive refine— around each promising probe, densify the cheap proxy to
                       find the bubble-richest frame and catch windows that
                       straddle a probe.
  L2  confirm        — run the EXPENSIVE validator on candidates best-first and
                       return the first that passes. ~O(1) validations in the
                       common (clustered) case.
  fallback           — a dense (stride-1) cheap pass guarantees completeness over
                       the set of frames whose proxy clears the threshold.

Correctness
-----------
- **Soundness is free**: a frame is only ever *returned* after the injected
  ``is_valid`` confirms it. Blocks/proxy only change *which* frames we try and in
  *what order*; they can never return an invalid frame.
- **Completeness** depends on coverage. The proxy must be a SOUND necessary
  condition (``is_valid(r)`` ⟹ ``cheap_count(r) >= tau``) or a valid frame could
  be wrongly skipped. And a probe ``stride`` only guarantees catching bubble
  windows *longer than* ``stride`` — see ``find_reference_frame`` notes on short
  windows.

The validation algorithm itself is **never defined or modified here** — it is
injected as the ``is_valid`` callable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ReferenceSearchStats:
    """Bookkeeping for a search (mostly to prove the speed-up in tests/logs)."""
    cheap_reads: int = 0          # number of distinct cheap_count() evaluations
    validations: int = 0          # number of distinct is_valid() evaluations
    probes_considered: int = 0    # promising L0 probes that were refined
    found_index: Optional[int] = None
    fallback_used: bool = False
    probe_scores: dict = field(default_factory=dict)  # frame -> cheap score (sparse)


def _refine_block(center: int, n: int, radius: int, cheap, tau: float) -> list[int]:
    """Cheap-probe the window [center-radius+1, center+radius-1] and return frames
    whose proxy clears ``tau``, richest first. Catches a window that straddles the
    probe and locates the bubble-richest frame within the block."""
    lo = max(0, center - radius + 1)
    hi = min(n - 1, center + radius - 1)
    scored = []
    for r in range(lo, hi + 1):
        sc = cheap(r)
        if sc is not None and sc >= tau:
            scored.append((sc, r))
    scored.sort(reverse=True)
    return [r for _sc, r in scored]


def find_reference_frame(
    n_frames: int,
    *,
    is_valid: Callable[[int], bool],
    cheap_count: Optional[Callable[[int], float]] = None,
    stride: int = 1,
    tau: float = 1.0,
    refine_radius: Optional[int] = None,
    max_validations: Optional[int] = None,
    exhaustive_fallback: bool = True,
) -> tuple[Optional[int], ReferenceSearchStats]:
    """Find the index of a valid reference frame, minimizing ``is_valid`` calls.

    Parameters
    ----------
    n_frames:
        Number of (index-aligned, across all cameras) frames to search.
    is_valid:
        EXPENSIVE black-box validator, ``is_valid(r) -> bool``. **Never modified.**
        A frame is only returned after this confirms it.
    cheap_count:
        Optional CHEAP proxy, ``cheap_count(r) -> float`` — a *sound necessary
        condition* for validity (``is_valid(r)`` ⟹ ``cheap_count(r) >= tau``),
        e.g. the min across cameras of the 2D bubble count. Frames scoring below
        ``tau`` are pruned without validation. If ``None``, the search degenerates
        to jump-search over ``is_valid`` (early-exit win only).
    stride:
        Coarse probe spacing ``s``. **Guarantees catching any bubble window longer
        than ``s``**; windows of length ``<= s`` can be missed by the coarse pass
        (the dense fallback then catches them when a proxy is supplied). Set
        ``s <= shortest window you must catch`` (derive from bubble persistence ×
        fps). The conceptual block size is ``2*s - 1`` (the refine window).
    tau:
        Proxy threshold = validation's true minimum bubble count (a *lower* bound,
        so the proxy never wrongly skips a valid frame).
    refine_radius:
        Half-width of the L1 refine window around a promising probe. Defaults to
        ``stride`` (blocks tile). Set smaller to bound refine cost when the cheap
        proxy is itself expensive (it decouples refine cost from the coarse
        miss-guarantee ``stride``).
    max_validations:
        Optional cap on expensive validations (returns ``None`` if exhausted).
    exhaustive_fallback:
        If True (default), guarantee completeness: when the coarse/refine phase
        finds nothing, run a dense (stride-1) cheap pass and validate every
        ``>= tau`` frame best-first. Set False to keep it strictly sub-linear at
        the cost of possibly missing very short windows.

    Returns
    -------
    (frame_index or None, stats)
    """
    stats = ReferenceSearchStats()
    if n_frames <= 0:
        return None, stats
    s = max(1, int(stride))
    rad = s if refine_radius is None else max(1, int(refine_radius))

    _cheap_cache: dict[int, Optional[float]] = {}
    _valid_cache: dict[int, bool] = {}

    def cheap(r: int) -> Optional[float]:
        if cheap_count is None:
            return None
        if r not in _cheap_cache:
            val = float(cheap_count(r))
            _cheap_cache[r] = val
            stats.cheap_reads += 1
            stats.probe_scores[r] = val
        return _cheap_cache[r]

    def valid(r: int) -> bool:
        if r in _valid_cache:
            return _valid_cache[r]
        if max_validations is not None and stats.validations >= max_validations:
            return False
        res = bool(is_valid(r))
        _valid_cache[r] = res
        stats.validations += 1
        return res

    # ------------------------------------------------------------------ #
    # No proxy: jump-search at stride, then full-scan fallback.          #
    # (Without a cheap proxy you cannot beat O(N) validations in the     #
    #  worst case; the only win is an early exit on a lucky probe.)      #
    # ------------------------------------------------------------------ #
    if cheap_count is None:
        for r in range(0, n_frames, s):
            if valid(r):
                stats.found_index = r
                return r, stats
        if exhaustive_fallback:
            for r in range(n_frames):
                if valid(r):
                    stats.found_index = r
                    stats.fallback_used = True
                    return r, stats
        return None, stats

    # ------------------------------------------------------------------ #
    # Proxy available: coarse-to-fine.                                   #
    # ------------------------------------------------------------------ #
    # L0: cheap probes at stride s (covers every window longer than s).
    probe_scores = [(cheap(r), r) for r in range(0, n_frames, s)]
    # Rank promising probes (>= tau) richest first.
    promising = sorted(
        ((sc, r) for sc, r in probe_scores if sc is not None and sc >= tau),
        reverse=True,
    )

    tried: set[int] = set()
    for _sc, r in promising:
        stats.probes_considered += 1
        # L1 refine + L2 confirm: validate the richest candidates in this block
        # first, returning on the first frame the real validator accepts.
        for cand in _refine_block(r, n_frames, rad, cheap, tau):
            if cand in tried:
                continue
            tried.add(cand)
            if valid(cand):
                stats.found_index = cand
                return cand, stats

    # ------------------------------------------------------------------ #
    # Fallback: dense (stride-1) cheap pass -> validate every >= tau      #
    # frame best-first. Guarantees no window above tau is missed.        #
    # ------------------------------------------------------------------ #
    if exhaustive_fallback:
        dense = []
        for r in range(n_frames):
            sc = cheap(r)
            if sc is not None and sc >= tau and r not in tried:
                dense.append((sc, r))
        dense.sort(reverse=True)
        for _sc, r in dense:
            if valid(r):
                stats.found_index = r
                stats.fallback_used = True
                return r, stats

    return None, stats


def find_reference_frame_blocks(
    n_frames: int,
    *,
    is_valid: Callable[[int], bool],
    cheap_count: Callable[[int], float],
    block_size: int,
    tau: float = 1.0,
    subdiv: int = 5,
    min_block: int = 1,
    max_validations: Optional[int] = None,
) -> tuple[Optional[int], ReferenceSearchStats]:
    """Multi-resolution coarse-to-fine block search (complete).

    Probes frames at **progressively finer** strides — ``block_size``, then
    ``block_size/subdiv``, then ``/subdiv`` again, … down to ``min_block`` (and a
    final stride of ``min_block``). At each newly-probed frame the cheap proxy
    runs; if it clears ``tau`` the (unchanged, injected) ``is_valid`` confirms it,
    returning on the first that passes. Each frame is probed **at most once**
    (a ``probed`` set dedupes across levels).

    This means: if the coarse block heads all score below ``tau`` (e.g. every
    block's first frame triangulates nothing), the search does **not** fail — it
    shrinks the block and probes the in-between frames, and only reports "no valid
    frame" once **every frame down to ``min_block``** has been cheap-probed
    (``min_block=1`` ⇒ all frames). A valid frame at a coarse position is still
    found fast (early levels), so the full sweep only happens when failing.

    Cost: with ``min_block=1`` the cheap proxy is evaluated on every frame in the
    no-valid case (``O(n)`` cheap probes — same order as the original frame-by-
    frame scan, but without the expensive retry ladder); the expensive
    ``is_valid`` is still only ever run on frames whose cheap score ``>= tau``
    (zero of them when nothing triangulates). Set ``min_block > 1`` to stop
    shrinking early (``~n/min_block`` cheap probes, sub-complete) if you want a
    bounded scan.

    ``is_valid`` is **never modified** — only the scan order/gating around it.
    Pick ``tau`` = the validator's true minimum (so the gate is sound) and
    ``block_size`` ≈ shortest bubble window (e.g. ``fps/5``).

    Returns ``(frame_index or None, stats)``.
    """
    stats = ReferenceSearchStats()
    if n_frames <= 0:
        return None, stats
    bs = max(1, int(block_size))
    sub = max(2, int(subdiv))
    mb = max(1, int(min_block))

    _valid_cache: dict[int, bool] = {}

    def valid(r: int) -> bool:
        if r in _valid_cache:
            return _valid_cache[r]
        if max_validations is not None and stats.validations >= max_validations:
            return False
        res = bool(is_valid(r))
        _valid_cache[r] = res
        stats.validations += 1
        return res

    # Build the coarse-to-fine stride schedule: bs, bs/sub, bs/sub^2, ..., >= mb,
    # with a final stride of mb so coverage is complete down to min_block.
    strides = []
    s = bs
    while True:
        strides.append(s)
        if s <= mb:
            break
        s = max(mb, s // sub)
        if strides and s == strides[-1]:
            break
    if strides[-1] != mb:
        strides.append(mb)

    probed: set[int] = set()
    for s in strides:
        for f in range(0, n_frames, s):
            if f in probed:
                continue
            probed.add(f)
            sc = float(cheap_count(f))
            stats.cheap_reads += 1
            stats.probe_scores[f] = sc
            if sc >= tau:
                stats.probes_considered += 1
                if valid(f):
                    stats.found_index = f
                    return f, stats
    return None, stats


# --------------------------------------------------------------------------- #
# Practical defaults for the image-preprocessing context: per-camera frame    #
# readers + a sound cheap bubble-count proxy.                                  #
# --------------------------------------------------------------------------- #
def build_frame_readers(detected, frames: Optional[tuple[int, int]] = None):
    """Return ``(readers, n_frames)`` for a ``DetectedRootInput``.

    ``readers[c](r) -> grayscale ndarray`` reads frame ``r`` of camera ``c``.
    Frames are index-aligned across cameras; ``n_frames`` is the min count.
    """
    import numpy as np  # noqa: F401  (kept local; module core stays dependency-free)

    readers = []
    lengths = []
    if getattr(detected, "input_kind", None) == "cine":
        if frames is None:
            raise ValueError("frames=(start, end) is required for CINE inputs")
        start, end = frames
        n = end - start + 1
        from .io import read_cine_frame
        for cam in detected.cameras:
            if cam.cine_path is None:
                raise ValueError(f"CINE camera has no path: {cam.camera_name}")
            readers.append(lambda r, p=cam.cine_path, b=start: _to_gray(read_cine_frame(p, b + r)))
            lengths.append(n)
    else:
        for cam in detected.cameras:
            paths = list(cam.image_paths)
            readers.append(lambda r, ps=paths: _imread_gray(ps[r]))
            lengths.append(len(paths))
    return readers, (min(lengths) if lengths else 0)


def _imread_gray(path):
    import cv2
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise IOError(f"Failed to read image: {path}")
    return _to_gray(img)


def _to_gray(img):
    import cv2
    import numpy as np
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype != np.uint8:
        m = float(img.max()) or 1.0
        img = (img.astype(np.float32) / m * 255.0).astype(np.uint8)
    return img


def make_bubble_count_proxy(
    readers,
    *,
    invert: bool = False,
    threshold="otsu",
    min_blob_area: int = 4,
    max_blob_area: Optional[int] = None,
):
    """Build a sound cheap proxy ``cheap_count(r) -> int``.

    Reads frame ``r`` from every camera, thresholds, counts connected components
    in the allowed area range, and returns the **min across cameras** (a bubble
    must be visible in every camera to be triangulated, so the min is a necessary
    condition for the downstream validation).

    Tune ``invert`` (bright vs dark bubbles), ``threshold`` ("otsu" or an int),
    and ``min_blob_area`` so the count does **not** under-report bubbles (an
    under-count would wrongly prune valid frames). Pair with a ``tau`` set to the
    validator's true minimum bubble count.
    """
    import cv2

    def _count(img) -> int:
        g = (255 - img) if invert else img
        if threshold == "otsu":
            _t, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _t, bw = cv2.threshold(g, int(threshold), 255, cv2.THRESH_BINARY)
        num, _lbl, cc_stats, _cent = cv2.connectedComponentsWithStats(bw, connectivity=8)
        c = 0
        for i in range(1, num):  # 0 = background
            area = int(cc_stats[i, cv2.CC_STAT_AREA])
            if area >= min_blob_area and (max_blob_area is None or area <= max_blob_area):
                c += 1
        return c

    def cheap_count(r: int) -> int:
        return min(_count(rd(r)) for rd in readers)

    return cheap_count


def make_stereomatch_count3d_proxy(lpt, camera_models, obj_cfg, imgio_list, num_cams,
                                   tol_2d_px=None, tol_3d_mm=None):
    """Build the recommended cheap proxy ``cheap_count(frame) -> int = count_3d``.

    For one frame: load each camera image, run 2D detection, then a **single**
    ``StereoMatch().match()`` (NO tolerance retry ladder) and return the number of
    matched 3D objects. This is ~10x cheaper than the full validation (which
    retries the match ~17x and then runs ``calBubbleRefImg``) yet is the *actual*
    triangulation signal — far more predictive of validity than a 2D bubble count.

    ``tol_2d_px`` / ``tol_3d_mm`` (optional) set the StereoMatch tolerances for the
    probe and are **restored** afterwards. Pass the validator's *maximum* retry
    tolerances here to make the gate **sound**: if even at the loosest tolerance a
    frame yields ``count_3d <= 5``, no validation attempt could pass, so it is safe
    to prune without ever calling the expensive validator.

    It reuses the same ``lpt`` primitives the validator uses but is a **separate
    function**: the original validation routine (``_run_validation_on_frame`` /
    ``calBubbleRefImg``) is not modified or called here.

    Returns 0 if any camera has no 2D detections (a frame that can't triangulate).
    """
    finder = lpt.ObjectFinder2D()

    def cheap_count(frame_id: int) -> int:
        obj2d_list = []
        for cam_id in range(num_cams):
            img = imgio_list[cam_id].loadImg(frame_id)
            obj2ds = finder.findObject2D(img, obj_cfg)
            if len(obj2ds) == 0:
                return 0  # no triangulation possible if a camera sees nothing
            obj2d_list.append(obj2ds)
        save2d = obj_cfg._sm_param.tol_2d_px
        save3d = obj_cfg._sm_param.tol_3d_mm
        try:
            if tol_2d_px is not None:
                obj_cfg._sm_param.tol_2d_px = float(tol_2d_px)
            if tol_3d_mm is not None:
                obj_cfg._sm_param.tol_3d_mm = float(tol_3d_mm)
            obj3d_list = lpt.StereoMatch(camera_models, obj2d_list, obj_cfg).match()
        except Exception:
            return 0
        finally:
            obj_cfg._sm_param.tol_2d_px = save2d
            obj_cfg._sm_param.tol_3d_mm = save3d
        return len(obj3d_list)

    return cheap_count

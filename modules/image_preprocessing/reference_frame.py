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
        for cand in _refine_block(r, n_frames, s, cheap, tau):
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

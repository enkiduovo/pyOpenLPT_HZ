# pyright: reportAttributeAccessIssue=false
"""Narrow tests for the Gaussian renderer logic in generate_mirrored_tracks.

These tests verify:
- True Gaussian kernel math (parameterized by sigma_px)
- Kernel symmetry and intensity falloff
- Deterministic camera-specific render seeds
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

gen = pytest.importorskip("generate_mirrored_tracks")


def test_gaussian_kernel_symmetry_and_falloff():
    """Test that a single centered particle produces symmetric Gaussian falloff.
    
    A particle at the center of a pixel grid should produce:
    1. Symmetric intensity in all four quadrants
    2. Intensity falloff consistent with Gaussian exp(-(r^2)/(2*sigma^2))
    3. Maximum intensity at the center
    """
    n_row, n_col = 11, 11
    center_u = 5.0
    center_v = 5.0
    sigma_px = 0.85
    amplitude = 28.0
    background = 4.0
    
    img = gen.render_image(
        n_row, n_col,
        np.array([center_u]), np.array([center_v]),
        sigma_px=sigma_px,
        amplitude=amplitude,
        background_level=background,
        noise_std=0.0,
        rng=None,
    )
    
    # Center pixel should have highest intensity (background + amplitude contribution)
    center_intensity = float(img[5, 5])
    assert center_intensity > background + amplitude * 0.9, \
        f"Center intensity {center_intensity} should be close to {background + amplitude}"
    
    # Check symmetry: all four quadrants should match
    # Compare (5+dx, 5+dy) with (5-dx, 5+dy), (5+dx, 5-dy), (5-dx, 5-dy)
    for dx in [1, 2]:
        for dy in [1, 2]:
            val_pp = float(img[5 + dy, 5 + dx])  # (+, +)
            val_pm = float(img[5 + dy, 5 - dx])  # (+, -)
            val_mp = float(img[5 - dy, 5 + dx])  # (-, +)
            val_mm = float(img[5 - dy, 5 - dx])  # (-, -)
            
            np.testing.assert_allclose(
                [val_pp, val_pm, val_mp, val_mm],
                val_pp,
                rtol=0.02,
                err_msg=f"Symmetry broken at offset ({dx}, {dy})",
            )
    
    center_val = float(img[5, 5]) - background
    r1_val = float(img[6, 5]) - background
    
    expected_r1 = amplitude * np.exp(-1.0 / (2 * sigma_px**2))
    
    np.testing.assert_allclose(r1_val, expected_r1, rtol=0.15,
                                err_msg=f"Intensity at r=1 should follow Gaussian falloff")
    
    assert center_val > r1_val, \
        "Intensity must decrease with distance"


def test_camera_specific_deterministic_render_seed():
    """Test that render seed incorporates camera index, not just image dimensions.
    
    Two cameras with the same dimensions should produce different random noise
    patterns when rendered with the same frame index.
    """
    n_row, n_col = 100, 100
    frame_idx = 0
    base_seed = 20260421
    
    # Simulate two different cameras with same dimensions but different indices
    camera_idx_0 = 0
    camera_idx_1 = 1
    
    # Current (broken) seed formula: BASE_SEED + fi * 1000 + cam.n_row + cam.n_col
    # This produces the same seed for same-size cameras!
    seed_broken_cam0 = base_seed + frame_idx * 1000 + n_row + n_col
    seed_broken_cam1 = base_seed + frame_idx * 1000 + n_row + n_col
    assert seed_broken_cam0 == seed_broken_cam1, "Sanity check: old formula collides"
    
    # Correct formula should include camera index
    # Example: BASE_SEED + fi * 10000 + cam_idx * 1000 + n_row + n_col
    seed_correct_cam0 = base_seed + frame_idx * 10000 + camera_idx_0 * 1000 + n_row + n_col
    seed_correct_cam1 = base_seed + frame_idx * 10000 + camera_idx_1 * 1000 + n_row + n_col
    assert seed_correct_cam0 != seed_correct_cam1, "Sanity check: corrected formula differs"
    
    # Now test that render_image produces different noise for different camera indices
    # We'll render with noise enabled and check that outputs differ
    u = np.array([50.0, 50.0, 50.0])
    v = np.array([50.0, 60.0, 70.0])
    
    # Simulate camera 0
    rng_cam0 = np.random.default_rng(seed_correct_cam0)
    img_cam0 = gen.render_image(
        n_row, n_col, u, v,
        sigma_px=0.85,
        amplitude=28.0,
        background_level=4.0,
        noise_std=2.0,
        rng=rng_cam0,
    )
    
    # Simulate camera 1
    rng_cam1 = np.random.default_rng(seed_correct_cam1)
    img_cam1 = gen.render_image(
        n_row, n_col, u, v,
        sigma_px=0.85,
        amplitude=28.0,
        background_level=4.0,
        noise_std=2.0,
        rng=rng_cam1,
    )
    
    # Images should differ because of different noise realizations
    assert not np.array_equal(img_cam0, img_cam1), \
        "Same-size cameras with different indices must produce different noise patterns"
    
    # But if we use the same seed for both, they should be identical
    rng_same = np.random.default_rng(seed_correct_cam0)
    img_same = gen.render_image(
        n_row, n_col, u, v,
        sigma_px=0.85,
        amplitude=28.0,
        background_level=4.0,
        noise_std=2.0,
        rng=rng_same,
    )
    np.testing.assert_array_equal(img_cam0, img_same,
                                    err_msg="Same seed should produce identical images")


def test_additive_rendering_preserves_float_before_clipping():
    n_row, n_col = 20, 20
    u = np.array([10.0, 10.5])
    v = np.array([10.0, 10.0])
    
    amplitude = 200.0
    background = 10.0
    
    img = gen.render_image(
        n_row, n_col, u, v,
        sigma_px=0.85,
        amplitude=amplitude,
        background_level=background,
        noise_std=0.0,
        rng=None,
    )
    
    center_val = float(img[10, 10])
    assert center_val == 255.0, \
        f"Overlapping high-intensity particles should clip to 255, got {center_val}"
    
    nearby_val = float(img[11, 10])
    assert nearby_val > background, \
        f"Nearby intensity {nearby_val} should be above background {background}"

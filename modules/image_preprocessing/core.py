# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
"""
Image Preprocessing Core
Pure processing functions with no GUI dependencies.
Extracted for CLI and programmatic use.
"""

import numpy as np
import cv2


DEFAULT_PROCESSING_SETTINGS = {
    "bg_enabled": False,
    "invert": False,
    "cine_shifts": {},
    "low_in": 0,
    "high_in": 255,
    "denoise": False,
}


def normalize_processing_settings(settings=None):
    """
    Normalize preprocessing settings for CLI and GUI callers.

    Parameters
    ----------
    settings : dict or None
        Partial or complete settings dictionary.

    Returns
    -------
    dict
        Settings dictionary with all required keys populated.
    """
    normalized = dict(DEFAULT_PROCESSING_SETTINGS)
    if settings:
        normalized.update(settings)

    cine_shifts = normalized.get("cine_shifts") or {}
    normalized["cine_shifts"] = dict(cine_shifts)
    return normalized


def imadjust_opencv(img, low_in, high_in, low_out=0, high_out=255, gamma=1.0):
    """
    Adjust image intensity values similar to MATLAB's imadjust.
    
    Parameters
    ----------
    img : ndarray
        Input image (uint8 or float)
    low_in : float
        Lower input intensity limit
    high_in : float
        Upper input intensity limit
    low_out : float, optional
        Lower output intensity limit (default: 0)
    high_out : float, optional
        Upper output intensity limit (default: 255)
    gamma : float, optional
        Gamma correction value (default: 1.0)
    
    Returns
    -------
    ndarray
        Adjusted image as uint8
    """
    # Ensure float for calculation
    img = img.astype(np.float32)

    # normalize to [0,1]
    # Handle division by zero
    diff = high_in - low_in
    if diff < 1e-5:
        diff = 1e-5
        
    img = (img - low_in) / diff
    img = np.clip(img, 0, 1)

    # gamma
    if gamma != 1.0:
        img = img ** gamma

    # scale to output range
    img = img * (high_out - low_out) + low_out
    img = np.clip(img, low_out, high_out)

    return img.astype(np.uint8)


def apply_processing_pipeline_with_settings(img_data, bg_data, cam_idx, settings):
    """
    Apply complete image preprocessing pipeline.
    
    Pure processing pipeline for worker thread use or CLI processing.
    
    Parameters
    ----------
    img_data : ndarray
        Input image data (grayscale or color, any bit depth)
    bg_data : ndarray or None
        Background image for subtraction (float32), or None to skip
    cam_idx : int
        Camera index for bit-shift lookup
    settings : dict
        Processing settings dictionary with keys:
        - bg_enabled : bool
            Enable background subtraction
        - invert : bool
            Invert image intensities
        - cine_shifts : dict
            {cam_idx: shift_bits} for bit-depth reduction
        - low_in : float
            Lower input range for intensity adjustment
        - high_in : float
            Upper input range for intensity adjustment
        - denoise : bool
            Enable enhanced denoise processing
    
    Returns
    -------
    ndarray
        Processed image as uint8
    """
    settings = normalize_processing_settings(settings)

    # 0. Ensure grayscale and float32
    if len(img_data.shape) == 3:
        gray = cv2.cvtColor(img_data, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        gray = img_data.astype(np.float32)

    # 1. Background Subtraction (float32)
    if settings["bg_enabled"] and bg_data is not None:
        if settings["invert"]:
            result = bg_data - gray
        else:
            result = gray - bg_data
        result = np.clip(result, 0, None)
    else:
        result = gray

    # 2. Bit shift to 8-bit
    shift = settings["cine_shifts"].get(cam_idx, 0)
    if shift > 0:
        result = (result / (2 ** shift))
    result = np.clip(result, 0, 255).astype(np.uint8)

    # 3. Invert (only if not already handled by BG subtraction)
    if settings["invert"] and not (settings["bg_enabled"] and bg_data is not None):
        result = 255 - result

    # 4. Range adjustment
    result = imadjust_opencv(result, settings["low_in"], settings["high_in"])

    # 5. Denoise
    if settings["denoise"]:
        a = result.astype(np.float32)
        kernel = np.ones((3, 3), np.uint8)
        b = cv2.erode(a, kernel, iterations=1)
        c = a - b
        b = cv2.erode(a, kernel, iterations=1)
        c = c - b

        d = cv2.GaussianBlur(c, (0, 0), 0.5)
        e = cv2.blur(d, (100, 100))
        f = a - e

        blurred_f = cv2.GaussianBlur(f, (0, 0), 1.0)
        sharp = f + 0.8 * (f - blurred_f)
        result = np.clip(sharp, 0, 255).astype(np.uint8)

    return result.astype(np.uint8)

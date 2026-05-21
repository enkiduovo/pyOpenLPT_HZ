# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
import sys
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from modules.image_preprocessing.core import apply_processing_pipeline_with_settings


def test_apply_processing_pipeline_inverts_uint8_images_without_background():
    image = np.array([[0, 64], [128, 255]], dtype=np.uint8)

    result = apply_processing_pipeline_with_settings(
        image,
        bg_data=None,
        cam_idx=1,
        settings={"invert": True, "low_in": 0, "high_in": 255},
    )

    expected = np.array([[255, 191], [127, 0]], dtype=np.uint8)
    np.testing.assert_array_equal(result, expected)


def test_apply_processing_pipeline_subtracts_mean_background_and_clips_negative_values():
    image = np.array([[10, 20], [40, 50]], dtype=np.uint8)
    background = np.array([[2, 5], [10, 60]], dtype=np.float32)

    result = apply_processing_pipeline_with_settings(
        image,
        bg_data=background,
        cam_idx=1,
        settings={"bg_enabled": True, "low_in": 0, "high_in": 255},
    )

    expected = np.array([[8, 15], [30, 0]], dtype=np.uint8)
    np.testing.assert_array_equal(result, expected)

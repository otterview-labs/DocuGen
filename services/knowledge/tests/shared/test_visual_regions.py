from __future__ import annotations

import pytest

from app.shared.utils.visual_regions import (
    build_full_region_definition,
    build_region_external_key,
    normalize_bbox,
    normalize_external_visual_regions,
)


pytestmark = pytest.mark.unit


def test_normalize_bbox_accepts_pixel_xyxy() -> None:
    bbox = normalize_bbox([20, 10, 120, 60], coord_space="pixel", width=200, height=100)

    assert bbox == [0.1, 0.1, 0.6, 0.6]


def test_build_region_external_key_is_stable_for_same_payload() -> None:
    region = {
        "region_type": "bbox",
        "source_system": "upstream-a",
        "label": "screen",
        "bbox": [0.1, 0.2, 0.4, 0.8],
    }

    key_a = build_region_external_key(region, [0.1, 0.2, 0.4, 0.8])
    key_b = build_region_external_key(region, [0.1, 0.2, 0.4, 0.8])

    assert key_a == key_b
    assert len(key_a) == 40


def test_build_full_region_definition_covers_entire_image() -> None:
    region = build_full_region_definition()

    assert region["region_type"] == "full"
    assert region["bbox_normalized"] == [0.0, 0.0, 1.0, 1.0]
    assert region["external_key"] == "__full__"


def test_normalize_external_visual_regions_supports_xywh_pixels() -> None:
    regions = normalize_external_visual_regions(
        [
            {
                "bbox": {"x": 10, "y": 20, "w": 40, "h": 30},
                "label": "device",
                "source_system": "biz-a",
            }
        ],
        width=100,
        height=100,
        default_source_system="fallback",
    )

    assert len(regions) == 1
    assert regions[0]["bbox_normalized"] == [0.1, 0.2, 0.5, 0.5]
    assert regions[0]["label"] == "device"
    assert regions[0]["source_system"] == "biz-a"

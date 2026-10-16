#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉 region 工具。

职责：
- 统一外部传入 bbox 的格式
- 将像素/归一化坐标转换为归一化 xyxy
- 生成稳定的外部幂等键
- 生成 region crop，供视觉向量化使用
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _round_bbox(values: Sequence[float]) -> List[float]:
    return [round(float(v), 6) for v in values]


def _coerce_bbox(bbox: Any) -> Optional[List[float]]:
    """将常见 bbox 输入统一转换为 xyxy。"""
    if bbox is None:
        return None

    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
        except Exception:
            return None

    if isinstance(bbox, dict):
        if {"x1", "y1", "x2", "y2"}.issubset(bbox.keys()):
            try:
                return [
                    float(bbox["x1"]),
                    float(bbox["y1"]),
                    float(bbox["x2"]),
                    float(bbox["y2"]),
                ]
            except Exception:
                return None
        if {"x", "y", "w", "h"}.issubset(bbox.keys()):
            try:
                x = float(bbox["x"])
                y = float(bbox["y"])
                w = float(bbox["w"])
                h = float(bbox["h"])
                return [x, y, x + w, y + h]
            except Exception:
                return None

    return None


def normalize_bbox(
    bbox: Any,
    *,
    coord_space: str = "pixel",
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Optional[List[float]]:
    """归一化 bbox 到 [0, 1] 的 xyxy。"""
    values = _coerce_bbox(bbox)
    if not values:
        return None

    x1, y1, x2, y2 = values
    coord_space = (coord_space or "pixel").strip().lower()

    if coord_space == "normalized":
        normalized = [x1, y1, x2, y2]
    else:
        if not width or not height or width <= 0 or height <= 0:
            return None
        normalized = [
            x1 / float(width),
            y1 / float(height),
            x2 / float(width),
            y2 / float(height),
        ]

    nx1, ny1, nx2, ny2 = normalized
    nx1 = _clamp(nx1, 0.0, 1.0)
    ny1 = _clamp(ny1, 0.0, 1.0)
    nx2 = _clamp(nx2, 0.0, 1.0)
    ny2 = _clamp(ny2, 0.0, 1.0)

    if nx2 <= nx1 or ny2 <= ny1:
        return None

    return _round_bbox([nx1, ny1, nx2, ny2])


def build_region_external_key(region: Dict[str, Any], normalized_bbox: Sequence[float]) -> str:
    """生成稳定的 region 幂等键。"""
    explicit_key = str(region.get("external_key") or "").strip()
    if explicit_key:
        return explicit_key[:128]

    explicit_region_id = str(region.get("region_id") or region.get("external_region_id") or "").strip()
    if explicit_region_id:
        return explicit_region_id[:128]

    signature = {
        "region_type": str(region.get("region_type") or "bbox").strip().lower() or "bbox",
        "source_system": str(region.get("source_system") or "").strip(),
        "label": str(region.get("label") or "").strip(),
        "bbox": list(normalized_bbox),
        "text": str(region.get("text") or region.get("region_text") or "").strip(),
    }
    digest = hashlib.sha1(
        json.dumps(signature, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return digest[:40]


def build_full_region_definition() -> Dict[str, Any]:
    """生成整图 region。"""
    return {
        "external_key": "__full__",
        "external_region_id": None,
        "region_type": "full",
        "coord_space": "normalized",
        "bbox_raw": [0.0, 0.0, 1.0, 1.0],
        "bbox_normalized": [0.0, 0.0, 1.0, 1.0],
        "label": None,
        "confidence": 1.0,
        "region_text": None,
        "source": "system",
        "source_system": "knowledge",
        "sort_order": 0,
        "metadata": {"generated": "full_region"},
    }


def normalize_external_visual_regions(
    regions: Sequence[Dict[str, Any]] | None,
    *,
    width: Optional[int],
    height: Optional[int],
    default_source_system: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """归一化外部传入的视觉 region 列表。"""
    normalized_regions: List[Dict[str, Any]] = []

    for index, raw_region in enumerate(list(regions or [])):
        if not isinstance(raw_region, dict):
            continue

        coord_space = str(raw_region.get("coord_space") or "pixel").strip().lower() or "pixel"
        bbox_input = raw_region.get("bbox")
        if bbox_input is None and raw_region.get("bbox_normalized") is not None:
            bbox_input = raw_region.get("bbox_normalized")
            coord_space = "normalized"
        elif bbox_input is None and raw_region.get("bbox_raw") is not None:
            bbox_input = raw_region.get("bbox_raw")

        raw_bbox = _coerce_bbox(bbox_input)
        normalized_bbox = normalize_bbox(
            raw_bbox,
            coord_space=coord_space,
            width=width,
            height=height,
        )
        if not normalized_bbox:
            continue

        external_key = build_region_external_key(raw_region, normalized_bbox)
        region_text = raw_region.get("text")
        if region_text is None:
            region_text = raw_region.get("region_text")

        normalized_regions.append(
            {
                "external_key": external_key,
                "external_region_id": str(
                    raw_region.get("region_id") or raw_region.get("external_region_id") or ""
                ).strip()
                or None,
                "region_type": str(raw_region.get("region_type") or "bbox").strip().lower() or "bbox",
                "coord_space": "normalized",
                "bbox_raw": _round_bbox(raw_bbox or normalized_bbox),
                "bbox_normalized": normalized_bbox,
                "label": str(raw_region.get("label") or "").strip() or None,
                "confidence": (
                    float(raw_region["confidence"]) if raw_region.get("confidence") is not None else None
                ),
                "region_text": str(region_text).strip() if region_text is not None and str(region_text).strip() else None,
                "source": "external",
                "source_system": str(raw_region.get("source_system") or default_source_system or "external").strip()
                or "external",
                "sort_order": int(raw_region.get("sort_order", index + 1)),
                "metadata": {
                    "input_coord_space": coord_space,
                    "raw_region": raw_region,
                },
            }
        )

    return normalized_regions


def load_image_size(image_path: str) -> tuple[int, int]:
    with Image.open(image_path) as image:
        width, height = image.size
    return int(width), int(height)


def crop_image_by_normalized_bbox(
    image_path: str,
    bbox_normalized: Sequence[float],
    *,
    padding_ratio: float = 0.06,
) -> Image.Image:
    """按归一化 bbox 裁剪图片，并保留一点边缘上下文。"""
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        width, height = image.size
        x1, y1, x2, y2 = [float(v) for v in bbox_normalized]

        pad_x = (x2 - x1) * float(padding_ratio)
        pad_y = (y2 - y1) * float(padding_ratio)

        px1 = int(round(_clamp(x1 - pad_x, 0.0, 1.0) * width))
        py1 = int(round(_clamp(y1 - pad_y, 0.0, 1.0) * height))
        px2 = int(round(_clamp(x2 + pad_x, 0.0, 1.0) * width))
        py2 = int(round(_clamp(y2 + pad_y, 0.0, 1.0) * height))

        if px2 <= px1:
            px2 = min(width, px1 + 1)
        if py2 <= py1:
            py2 = min(height, py1 + 1)

        return image.crop((px1, py1, px2, py2)).copy()


def resolve_upload_file_path(file_url: Optional[str]) -> Optional[str]:
    """将 /uploads/... 映射为本地文件路径。"""
    raw = str(file_url or "").strip()
    if not raw:
        return None

    prefixes = ("/uploads/", "/static/uploads/", "uploads/")
    if not raw.startswith(prefixes):
        return None

    filename = Path(raw.split("?", 1)[0].split("#", 1)[0]).name
    if not filename:
        return None

    candidate = (Path("storage/static/uploads") / filename).resolve()
    return str(candidate) if candidate.exists() else None

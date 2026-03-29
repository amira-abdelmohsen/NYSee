from __future__ import annotations

import re
from typing import Any

from google.cloud import vision


USEFUL_TEXT_KEYWORDS = {
    "street",
    "st",
    "ave",
    "avenue",
    "blvd",
    "boulevard",
    "sq",
    "square",
    "bridge",
    "park",
    "one way",
    "cross",
    "crosswalk",
    "transportation",
    "dept",
    "department",
    "broadway",
    "barclay",
    "brooklyn",
    "pierre",
}

PREFERRED_LABELS = {
    "street name sign",
    "traffic sign",
    "road sign",
    "signage",
    "traffic light",
    "crosswalk",
    "intersection",
    "road",
    "sidewalk",
    "building",
    "high-rise building",
}


def _extract_raw_text(response: vision.AnnotateImageResponse) -> str | None:
    if not response.text_annotations:
        return None

    raw_text = response.text_annotations[0].description or ""
    raw_text = raw_text.strip()
    return raw_text or None


def _normalize_for_dedupe(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _expand_for_speech(text: str) -> str:
    replacements = [
        (r"\bDEPT\.?\b", "Department"),
        (r"\bDOT\b", "Department of Transportation"),
        (r"\bSQ\b", "Square"),
        (r"\bST\b", "Street"),
        (r"\bAVE\b", "Avenue"),
        (r"\bBLVD\b", "Boulevard"),
        (r"\bPKWY\b", "Parkway"),
        (r"\bRD\b", "Road"),
        (r"\bCROS\b", "Crossing"),
        (r"\bCTR\b", "Center"),
    ]

    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # fix common OCR joined street abbreviations
    result = re.sub(r"BARCLAYST\b", "Barclay Street", result, flags=re.IGNORECASE)
    result = re.sub(r"\s+", " ", result).strip()

    return result


def _clean_for_display(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _merge_split_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    i = 0

    while i < len(lines):
        current = lines[i]

        if i + 1 < len(lines):
            nxt = lines[i + 1]
            combined = f"{current} {nxt}".strip()

            if _score_text_line(combined) >= max(_score_text_line(current), _score_text_line(nxt)):
                merged.append(combined)
                i += 2
                continue

        merged.append(current)
        i += 1

    return merged


def _clean_text_lines(text: str | None) -> list[str]:
    if not text:
        return []

    raw_lines = [line.strip() for line in text.splitlines()]
    cleaned: list[str] = []

    for line in raw_lines:
        if not line:
            continue

        line = re.sub(r"\s+", " ", line).strip()

        if len(line) <= 2:
            continue

        letters = sum(ch.isalpha() for ch in line)
        if letters < 2:
            continue

        cleaned.append(line)

    cleaned = _merge_split_lines(cleaned)

    deduped: list[str] = []
    seen: set[str] = set()

    for line in cleaned:
        norm = _normalize_for_dedupe(line)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        deduped.append(line)

    return deduped


def _score_text_line(line: str) -> int:
    score = 0
    lowered = line.lower()

    for keyword in USEFUL_TEXT_KEYWORDS:
        if keyword in lowered:
            score += 3

    if 4 <= len(line) <= 40:
        score += 2

    if any(ch.isalpha() for ch in line):
        score += 1

    digits = sum(ch.isdigit() for ch in line)
    if digits > 6:
        score -= 1

    if " " in line:
        score += 2

    # penalize obvious junk combinations
    if "facial" in lowered or "remix" in lowered:
        score -= 3

    return score


def _select_best_text_lines(text: str | None, max_lines: int = 4) -> list[str]:
    lines = _clean_text_lines(text)
    ranked = sorted(lines, key=_score_text_line, reverse=True)
    return ranked[:max_lines]


def _extract_labels(response: vision.AnnotateImageResponse) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []

    for label in response.label_annotations[:10]:
        description = (label.description or "").strip().lower()
        score = float(label.score or 0.0)

        if description:
            labels.append(
                {
                    "description": description,
                    "score": round(score, 3),
                }
            )

    return labels


def _extract_objects(response: vision.AnnotateImageResponse) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    seen: set[str] = set()

    for obj in response.localized_object_annotations[:10]:
        name = (obj.name or "").strip().lower()
        score = float(obj.score or 0.0)

        if not name:
            continue
        if name in seen:
            continue

        seen.add(name)
        objects.append(
            {
                "name": name,
                "score": round(score, 3),
            }
        )

    return objects


def _select_best_labels(labels: list[dict[str, Any]], max_labels: int = 3) -> list[str]:
    useful = [item for item in labels if item["description"] in PREFERRED_LABELS]
    useful.sort(key=lambda item: item["score"], reverse=True)

    # prefer navigation-relevant labels over generic skyline labels
    if useful:
        useful_names = [item["description"] for item in useful]
        if "street name sign" in useful_names:
            ordered = ["street name sign"] + [x for x in useful_names if x != "street name sign"]
            return ordered[:max_labels]
        return useful_names[:max_labels]

    return [item["description"] for item in labels[:max_labels]]


def _build_summary(
    labels: list[dict[str, Any]],
    objects: list[dict[str, Any]],
    text_lines: list[str],
) -> str:
    parts: list[str] = []

    best_labels = _select_best_labels(labels)

    if objects:
        object_names = [item["name"] for item in objects[:2]]
        if len(object_names) == 1:
            parts.append(f"Detected object: {object_names[0]}.")
        else:
            parts.append(f"Detected objects: {object_names[0]} and {object_names[1]}.")

    if best_labels:
        if len(best_labels) == 1:
            parts.append(f"Scene label: {best_labels[0]}.")
        else:
            parts.append(f"Scene labels: {', '.join(best_labels[:2])}.")

    if text_lines:
        parts.append(f"Most useful visible text: {'; '.join(text_lines[:3])}.")

    if not parts:
        return "The image was processed, but no clear objects, labels, or readable text were found."

    return " ".join(parts)


def _build_spoken_text(
    labels: list[dict[str, Any]],
    objects: list[dict[str, Any]],
    text_lines: list[str],
) -> str:
    parts: list[str] = []

    best_labels = _select_best_labels(labels)

    # Prefer helpful navigation language
    if "street name sign" in best_labels:
        parts.append("A street sign may be visible.")
    elif objects:
        object_names = [item["name"] for item in objects[:2]]
        if len(object_names) == 1:
            parts.append(f"I detected a {object_names[0]}.")
        else:
            parts.append(f"I detected a {object_names[0]} and a {object_names[1]}.")

    spoken_lines = [_expand_for_speech(_clean_for_display(line)) for line in text_lines[:3]]

    if spoken_lines:
        parts.append(f"Useful text includes {', '.join(spoken_lines[:-1]) + ', and ' + spoken_lines[-1] if len(spoken_lines) > 1 else spoken_lines[0]}.")

    if not parts:
        return "I could not find any clear objects or readable text in the image."

    return " ".join(parts)


def analyze_image_bytes(image_bytes: bytes) -> dict[str, Any]:
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)

    response = client.annotate_image(
        {
            "image": image,
            "features": [
                {"type_": vision.Feature.Type.OBJECT_LOCALIZATION, "max_results": 20},
                {"type_": vision.Feature.Type.LABEL_DETECTION, "max_results": 20},
                {"type_": vision.Feature.Type.TEXT_DETECTION, "max_results": 20},
            ],
        }
    )

    if response.error.message:
        raise RuntimeError(response.error.message)

    raw_text = _extract_raw_text(response)
    selected_text_lines = _select_best_text_lines(raw_text, max_lines=5)
    objects = _extract_objects(response)
    labels = _extract_labels(response)

    summary = _build_summary(labels, objects, selected_text_lines)
    spoken_text = _build_spoken_text(labels, objects, selected_text_lines)

    return {
        "mode": "image_only",
        "summary_text": summary,
        "spoken_text": spoken_text,
        "objects": objects,
        "labels": labels,
        "text": raw_text,
        "selected_text_lines": selected_text_lines,
    }
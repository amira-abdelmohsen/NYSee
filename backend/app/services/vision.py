from __future__ import annotations

from typing import Any

from google.cloud import vision

RELEVANT_LABELS = {
    "crosswalk",
    "traffic light",
    "street sign",
    "stop sign",
    "road",
    "sidewalk",
    "intersection",
    "pedestrian",
    "vehicle",
    "car",
    "bus",
    "bicycle",
    "building",
    "signage",
}



def _extract_best_text(response: vision.AnnotateImageResponse) -> str | None:
    if not response.text_annotations:
        return None

    raw_text = response.text_annotations[0].description or ""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return None

    return lines[0][:120]



def _extract_labels(response: vision.AnnotateImageResponse) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []

    for label in response.label_annotations:
        description = (label.description or "").strip().lower()
        score = float(label.score or 0.0)

        if score < 0.65:
            continue

        if description in RELEVANT_LABELS:
            filtered.append({
                "description": description,
                "score": round(score, 3),
            })

    if not filtered:
        # Fallback to the top 3 labels if nothing matched the allowlist.
        for label in response.label_annotations[:3]:
            description = (label.description or "").strip().lower()
            score = float(label.score or 0.0)
            if description:
                filtered.append({
                    "description": description,
                    "score": round(score, 3),
                })

    return filtered[:3]



def _build_summary(labels: list[dict[str, Any]], text: str | None) -> str:
    parts: list[str] = []

    if labels:
        label_names = [item["description"] for item in labels[:2]]
        if len(label_names) == 1:
            parts.append(f"Detected {label_names[0]}.")
        else:
            parts.append(f"Detected {label_names[0]} and {label_names[1]}.")

    if text:
        parts.append(f"Visible text says: {text}.")

    if not parts:
        return "The image was processed, but no clear labels or readable text were found."

    return " ".join(parts)



def analyze_image_bytes(image_bytes: bytes) -> dict[str, Any]:
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)

    response = client.annotate_image(
        {
            "image": image,
            "features": [
                {"type_": vision.Feature.Type.LABEL_DETECTION, "max_results": 5},
                {"type_": vision.Feature.Type.TEXT_DETECTION, "max_results": 5},
            ],
        }
    )

    if response.error.message:
        raise RuntimeError(response.error.message)

    labels = _extract_labels(response)
    text = _extract_best_text(response)
    summary = _build_summary(labels, text)

    return {
        "mode": "image_only",
        "summary_text": summary,
        "labels": labels,
        "text": text,
    }

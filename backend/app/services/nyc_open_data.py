# from __future__ import annotations

# import os
# from math import atan2, cos, radians, sin, sqrt
# from typing import Any

# import httpx

# APS_DATASET_URL = os.getenv(
#     "APS_DATASET_URL",
#     "https://data.cityofnewyork.us/resource/de3m-c5p4.json",
# )
# APS_APP_TOKEN = os.getenv("APS_APP_TOKEN")
# MAX_ROWS = int(os.getenv("APS_MAX_ROWS", "5000"))
# NEARBY_THRESHOLD_METERS = float(os.getenv("APS_NEARBY_THRESHOLD_METERS", "100"))



# def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
#     earth_radius_m = 6_371_000

#     dlat = radians(lat2 - lat1)
#     dlng = radians(lng2 - lng1)
#     a = (
#         sin(dlat / 2) ** 2
#         + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
#     )
#     c = 2 * atan2(sqrt(a), sqrt(1 - a))
#     return earth_radius_m * c



# def _safe_float(value: Any) -> float | None:
#     try:
#         if value is None or value == "":
#             return None
#         return float(value)
#     except (TypeError, ValueError):
#         return None



# def _extract_coords(row: dict[str, Any]) -> tuple[float, float] | None:
#     # Common Socrata patterns.
#     location = row.get("location")
#     if isinstance(location, dict):
#         lat = _safe_float(location.get("latitude"))
#         lng = _safe_float(location.get("longitude"))
#         if lat is not None and lng is not None:
#             return lat, lng

#         coordinates = location.get("coordinates")
#         if isinstance(coordinates, list) and len(coordinates) == 2:
#             lng = _safe_float(coordinates[0])
#             lat = _safe_float(coordinates[1])
#             if lat is not None and lng is not None:
#                 return lat, lng

#     for lat_key, lng_key in [
#         ("latitude", "longitude"),
#         ("lat", "lon"),
#         ("lat", "lng"),
#     ]:
#         lat = _safe_float(row.get(lat_key))
#         lng = _safe_float(row.get(lng_key))
#         if lat is not None and lng is not None:
#             return lat, lng

#     return None



# def _best_name(row: dict[str, Any]) -> str:
#     candidates = [
#         row.get("main_st"),
#         row.get("from_st"),
#         row.get("to_st"),
#         row.get("intersection"),
#         row.get("street_1"),
#         row.get("street_2"),
#         row.get("location_name"),
#         row.get("boro"),
#     ]
#     cleaned = [str(item).strip() for item in candidates if item and str(item).strip()]

#     if len(cleaned) >= 2:
#         return f"{cleaned[0]} and {cleaned[1]}"
#     if cleaned:
#         return cleaned[0]
#     return "Nearest APS location"


# async def _fetch_aps_rows() -> list[dict[str, Any]]:
#     headers = {"Accept": "application/json"}
#     if APS_APP_TOKEN:
#         headers["X-App-Token"] = APS_APP_TOKEN

#     params = {"$limit": str(MAX_ROWS)}

#     async with httpx.AsyncClient(timeout=15.0) as client:
#         response = await client.get(APS_DATASET_URL, params=params, headers=headers)
#         response.raise_for_status()
#         data = response.json()
#         if not isinstance(data, list):
#             raise RuntimeError("Unexpected APS dataset response shape.")
#         return data


# async def find_nearest_aps(user_lat: float, user_lng: float) -> dict[str, Any]:
#     rows = await _fetch_aps_rows()
#     candidates: list[dict[str, Any]] = []

#     for row in rows:
#         coords = _extract_coords(row)
#         if not coords:
#             continue

#         aps_lat, aps_lng = coords
#         distance = haversine_meters(user_lat, user_lng, aps_lat, aps_lng)
#         candidates.append(
#             {
#                 "name": _best_name(row),
#                 "distance_meters": round(distance, 1),
#                 "latitude": aps_lat,
#                 "longitude": aps_lng,
#             }
#         )

#     if not candidates:
#         return {
#             "mode": "location_only",
#             "summary_text": "No APS records with usable coordinates were found.",
#             "nearest_aps": None,
#             "nearby": False,
#         }

#     candidates.sort(key=lambda item: item["distance_meters"])
#     nearest = candidates[0]
#     nearby = nearest["distance_meters"] <= NEARBY_THRESHOLD_METERS

#     if nearby:
#         summary = (
#             f"The nearest accessible pedestrian signal is {nearest['distance_meters']} meters away "
#             f"at {nearest['name']}."
#         )
#     else:
#         summary = (
#             f"The closest accessible pedestrian signal in the dataset is {nearest['distance_meters']} meters away "
#             f"at {nearest['name']}."
#         )

#     return {
#         "mode": "location_only",
#         "summary_text": summary,
#         "nearest_aps": nearest,
#         "nearby": nearby,
#     }

import os
from math import radians, sin, cos, sqrt, atan2
from typing import Any, Dict, List, Optional, Tuple

import httpx

APS_DATASET_URL = os.getenv(
    "APS_DATASET_URL",
    "https://data.cityofnewyork.us/resource/de3m-c5p4.json",
)
APS_APP_TOKEN = os.getenv("APS_APP_TOKEN")


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance between two lat/lon points in meters."""
    r = 6371000  # Earth radius in meters

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def extract_coords(row: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """
    Extract (lat, lon) from a Socrata row.

    Primary expected format for this APS dataset:
    - the_geom: { "type": "Point", "coordinates": [lon, lat] }

    Fallbacks are included in case the dataset shape changes.
    """
    # Primary APS dataset geometry field
    geom = row.get("the_geom")
    if isinstance(geom, dict):
        coords = geom.get("coordinates")
        if isinstance(coords, list) and len(coords) == 2:
            try:
                lon = float(coords[0])
                lat = float(coords[1])
                return lat, lon
            except (TypeError, ValueError):
                pass

        lat = geom.get("latitude")
        lon = geom.get("longitude")
        if lat is not None and lon is not None:
            try:
                return float(lat), float(lon)
            except (TypeError, ValueError):
                pass

    # Common fallback pattern
    location = row.get("location")
    if isinstance(location, dict):
        lat = location.get("latitude")
        lon = location.get("longitude")
        if lat is not None and lon is not None:
            try:
                return float(lat), float(lon)
            except (TypeError, ValueError):
                pass

        coords = location.get("coordinates")
        if isinstance(coords, list) and len(coords) == 2:
            try:
                lon = float(coords[0])
                lat = float(coords[1])
                return lat, lon
            except (TypeError, ValueError):
                pass

    # Direct lat/lon fallback
    lat = row.get("latitude")
    lon = row.get("longitude")
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            pass

    return None


def extract_display_name(row: Dict[str, Any]) -> str:
    """
    Build a readable label for the APS location.
    Uses whichever fields are available.
    """
    candidate_fields = [
        "main_st",
        "from_st",
        "to_st",
        "street_1",
        "street_2",
        "intersection",
        "location_name",
        "boro",
        "corner",
    ]

    present_values: List[str] = []
    for field in candidate_fields:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            present_values.append(value.strip())

    if len(present_values) >= 2:
        return f"{present_values[0]} and {present_values[1]}"

    if len(present_values) == 1:
        return present_values[0]

    return "Accessible Pedestrian Signal location"


async def fetch_aps_rows(limit: int = 5000) -> List[Dict[str, Any]]:
    headers = {}
    if APS_APP_TOKEN:
        headers["X-App-Token"] = APS_APP_TOKEN

    params = {"$limit": limit}

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(APS_DATASET_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, list):
        return []

    return data


async def find_nearest_aps(latitude: float, longitude: float) -> Dict[str, Any]:
    rows = await fetch_aps_rows()

    candidates = []

    for row in rows:
        coords = extract_coords(row)
        if not coords:
            continue

        aps_lat, aps_lon = coords
        distance_meters = haversine_meters(latitude, longitude, aps_lat, aps_lon)

        candidates.append(
            {
                "name": extract_display_name(row),
                "distance_meters": round(distance_meters, 1),
                "coordinates": {
                    "latitude": aps_lat,
                    "longitude": aps_lon,
                },
                "raw_row": row,
            }
        )

    if not candidates:
        return {
            "mode": "location_only",
            "summary_text": "No APS records with usable coordinates were found.",
            "nearest_aps": None,
            "nearby": False,
        }

    candidates.sort(key=lambda item: item["distance_meters"])
    nearest = candidates[0]
    nearby = nearest["distance_meters"] <= 100

    return {
        "mode": "location_only",
        "summary_text": (
            f"The nearest accessible pedestrian signal is "
            f"{nearest['distance_meters']} meters away at {nearest['name']}."
        ),
        "nearest_aps": {
            "name": nearest["name"],
            "distance_meters": nearest["distance_meters"],
            "coordinates": nearest["coordinates"],
        },
        "nearby": nearby,
    }
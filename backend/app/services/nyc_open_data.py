from __future__ import annotations

import os
from math import radians, sin, cos, sqrt, atan2, degrees
from typing import Any, Dict, List, Optional, Tuple

import httpx

APS_DATASET_URL = os.getenv(
    "APS_DATASET_URL",
    "https://data.cityofnewyork.us/resource/de3m-c5p4.json",
)
APS_APP_TOKEN = os.getenv("APS_APP_TOKEN")
APS_NEARBY_THRESHOLD_METERS = float(os.getenv("APS_NEARBY_THRESHOLD_METERS", "100"))


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance between two lat/lon points in meters."""
    r = 6371000

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def initial_bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Bearing from point 1 to point 2.
    0 = north, 90 = east, 180 = south, 270 = west
    """
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dlambda = radians(lon2 - lon1)

    x = sin(dlambda) * cos(phi2)
    y = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dlambda)

    bearing = degrees(atan2(x, y))
    return (bearing + 360) % 360


def bearing_to_compass(bearing: float) -> str:
    directions = [
        "north",
        "northeast",
        "east",
        "southeast",
        "south",
        "southwest",
        "west",
        "northwest",
    ]
    index = round(bearing / 45) % 8
    return directions[index]


def extract_coords(row: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """
    Extract (lat, lon) from a Socrata row.
    Primary expected format:
    - the_geom: { "type": "Point", "coordinates": [lon, lat] }
    """
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

    lat = row.get("latitude")
    lon = row.get("longitude")
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            pass

    return None


def extract_intersection_name(row: Dict[str, Any]) -> str:
    """
    The dataset's readable intersection name is in `location`
    as a string. Fallback to other likely text fields if needed.
    """
    location_value = row.get("location")
    if isinstance(location_value, str) and location_value.strip():
        return location_value.strip()

    candidate_fields = [
        "intersection",
        "location_name",
        "main_st",
        "from_st",
        "to_st",
        "street_1",
        "street_2",
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

    return "the nearest APS intersection"


async def fetch_aps_rows(limit: int = 5000) -> List[Dict[str, Any]]:
    headers = {"Accept": "application/json"}
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


def build_location_summary(
    intersection_name: str,
    distance_meters: float,
    direction: str,
    nearby: bool,
) -> str:
    if nearby:
        return (
            f"The nearest accessible pedestrian signal is {distance_meters} meters away "
            f"to the {direction}, at {intersection_name}."
        )

    return (
        f"The closest accessible pedestrian signal in the dataset is {distance_meters} meters away "
        f"to the {direction}, at {intersection_name}."
    )


def build_location_spoken_text(
    intersection_name: str,
    distance_meters: float,
    direction: str,
    nearby: bool,
) -> str:
    rounded_distance = round(distance_meters)

    if nearby:
        return (
            f"The nearest accessible pedestrian signal is about {rounded_distance} meters away, "
            f"to the {direction}, at {intersection_name}."
        )

    return (
        f"The closest accessible pedestrian signal I found is about {rounded_distance} meters away, "
        f"to the {direction}, at {intersection_name}."
    )


async def find_nearest_aps(latitude: float, longitude: float) -> Dict[str, Any]:
    rows = await fetch_aps_rows()

    candidates = []

    for row in rows:
        coords = extract_coords(row)
        if not coords:
            continue

        aps_lat, aps_lon = coords
        distance_meters = haversine_meters(latitude, longitude, aps_lat, aps_lon)
        bearing_degrees = initial_bearing_degrees(latitude, longitude, aps_lat, aps_lon)
        direction = bearing_to_compass(bearing_degrees)
        intersection_name = extract_intersection_name(row)

        candidates.append(
            {
                "intersection_name": intersection_name,
                "distance_meters": round(distance_meters, 1),
                "bearing_degrees": round(bearing_degrees, 1),
                "direction": direction,
                "coordinates": {
                    "latitude": aps_lat,
                    "longitude": aps_lon,
                },
            }
        )

    if not candidates:
        return {
            "mode": "location_only",
            "summary_text": "No APS records with usable coordinates were found.",
            "spoken_text": "I could not find any accessible pedestrian signal records with usable coordinates.",
            "nearest_aps": None,
            "nearby": False,
        }

    candidates.sort(key=lambda item: item["distance_meters"])
    nearest = candidates[0]
    nearby = nearest["distance_meters"] <= APS_NEARBY_THRESHOLD_METERS

    summary_text = build_location_summary(
        nearest["intersection_name"],
        nearest["distance_meters"],
        nearest["direction"],
        nearby,
    )
    spoken_text = build_location_spoken_text(
        nearest["intersection_name"],
        nearest["distance_meters"],
        nearest["direction"],
        nearby,
    )

    return {
        "mode": "location_only",
        "summary_text": summary_text,
        "spoken_text": spoken_text,
        "nearest_aps": {
            "intersection_name": nearest["intersection_name"],
            "distance_meters": nearest["distance_meters"],
            "bearing_degrees": nearest["bearing_degrees"],
            "direction": nearest["direction"],
            "coordinates": nearest["coordinates"],
        },
        "nearby": nearby,
    }
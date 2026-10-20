
import asyncio
import json
import math
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def validate_coordinates(latitude: float, longitude: float) -> None:
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")

    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")


def calculate_distance_km(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    validate_coordinates(latitude1, longitude1)
    validate_coordinates(latitude2, longitude2)

    earth_radius_km = 6371.0

    lat1 = math.radians(latitude1)
    lat2 = math.radians(latitude2)
    lat_difference = math.radians(latitude2 - latitude1)
    lon_difference = math.radians(longitude2 - longitude1)

    a = (
        math.sin(lat_difference / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(lon_difference / 2) ** 2
    )

    a = min(1.0, max(0.0, a))
    distance = 2 * earth_radius_km * math.asin(math.sqrt(a))

    return round(distance, 3)


def _fetch_nearby_attractions(
    latitude: float,
    longitude: float,
    radius_m: int,
) -> list[dict]:
    query = f"""
    [out:json][timeout:20];
    (
      node["tourism"~"attraction|museum|viewpoint|zoo|theme_park"]
        (around:{radius_m},{latitude},{longitude});
      way["tourism"~"attraction|museum|viewpoint|zoo|theme_park"]
        (around:{radius_m},{latitude},{longitude});
      relation["tourism"~"attraction|museum|viewpoint|zoo|theme_park"]
        (around:{radius_m},{latitude},{longitude});
    );
    out center tags;
    """

    request = Request(
        OVERPASS_URL,
        data=query.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "StayNestPro/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "The mapping provider is temporarily unavailable."
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(
            "The mapping provider returned an invalid response."
        ) from exc

    attractions = []

    for item in data.get("elements", []):
        tags = item.get("tags", {})
        name = tags.get("name")

        if not name:
            continue

        item_latitude = item.get("lat")
        item_longitude = item.get("lon")

        if "center" in item:
            item_latitude = item["center"].get("lat")
            item_longitude = item["center"].get("lon")

        if item_latitude is None or item_longitude is None:
            continue

        distance = calculate_distance_km(
            latitude,
            longitude,
            float(item_latitude),
            float(item_longitude),
        )

        attractions.append(
            {
                "name": name,
                "type": tags.get("tourism", "attraction"),
                "latitude": item_latitude,
                "longitude": item_longitude,
                "distance_km": distance,
            }
        )

    attractions.sort(key=lambda attraction: attraction["distance_km"])
    return attractions


async def get_nearby_attractions(
    latitude: float,
    longitude: float,
    radius_m: int = 5000,
) -> list[dict]:
    validate_coordinates(latitude, longitude)

    if not 100 <= radius_m <= 50000:
        raise ValueError("Radius must be between 100 and 50000 metres.")

    return await asyncio.to_thread(
        _fetch_nearby_attractions,
        latitude,
        longitude,
        radius_m,
    )

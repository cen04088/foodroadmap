import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _to_local_xy_km(lat: float, lng: float, ref_lat: float) -> tuple[float, float]:
    x = math.radians(lng) * math.cos(math.radians(ref_lat)) * EARTH_RADIUS_KM
    y = math.radians(lat) * EARTH_RADIUS_KM
    return x, y


def project_point_onto_segment(
    point: tuple[float, float],
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
) -> tuple[float, float]:
    ref_lat = seg_start[0]

    px, py = _to_local_xy_km(point[0], point[1], ref_lat)
    ax, ay = _to_local_xy_km(seg_start[0], seg_start[1], ref_lat)
    bx, by = _to_local_xy_km(seg_end[0], seg_end[1], ref_lat)

    abx, aby = bx - ax, by - ay
    ab_len_sq = abx * abx + aby * aby

    if ab_len_sq == 0:
        t = 0.0
    else:
        apx, apy = px - ax, py - ay
        t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_len_sq))

    closest_x, closest_y = ax + t * abx, ay + t * aby
    distance_km = math.hypot(px - closest_x, py - closest_y)
    return distance_km, t


def bounding_box_with_margin(points: list[dict], margin_km: float) -> tuple[float, float, float, float]:
    lats = [p["lat"] for p in points]
    lngs = [p["lng"] for p in points]
    avg_lat = sum(lats) / len(lats)

    lat_margin_deg = margin_km / 111.0
    lng_margin_deg = margin_km / (111.320 * max(math.cos(math.radians(avg_lat)), 1e-9))

    return (
        min(lats) - lat_margin_deg,
        max(lats) + lat_margin_deg,
        min(lngs) - lng_margin_deg,
        max(lngs) + lng_margin_deg,
    )

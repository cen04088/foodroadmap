from dataclasses import dataclass

from app.geo import project_point_onto_segment
from app.models import Restaurant


@dataclass
class RestaurantMatch:
    restaurant: Restaurant
    distance_from_route_km: float
    cumulative_time_sec: float


def match_restaurants_to_route(
    route_points: list[dict],
    candidates: list[Restaurant],
    radius_km: float,
) -> list[RestaurantMatch]:
    if len(route_points) < 2:
        return []

    matches = []

    for restaurant in candidates:
        if restaurant.latitude is None or restaurant.longitude is None:
            continue

        best_distance_km = None
        best_time_sec = None

        for seg_start, seg_end in zip(route_points, route_points[1:]):
            distance_km, t = project_point_onto_segment(
                (restaurant.latitude, restaurant.longitude),
                (seg_start["lat"], seg_start["lng"]),
                (seg_end["lat"], seg_end["lng"]),
            )
            if best_distance_km is None or distance_km < best_distance_km:
                best_distance_km = distance_km
                best_time_sec = seg_start["cumulative_time_sec"] + t * (
                    seg_end["cumulative_time_sec"] - seg_start["cumulative_time_sec"]
                )

        if best_distance_km is not None and best_distance_km <= radius_km:
            matches.append(
                RestaurantMatch(
                    restaurant=restaurant,
                    distance_from_route_km=best_distance_km,
                    cumulative_time_sec=best_time_sec,
                )
            )

    matches.sort(key=lambda m: m.cumulative_time_sec)
    return matches

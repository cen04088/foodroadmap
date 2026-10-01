"""Conservative in-memory grouping; never rewrites the restaurant database."""
import re

from app.geo import haversine_km


def _text(value):
    return re.sub(r"\s+", "", value or "").casefold()


def _same_place(a, b):
    address = _text(a.get("address"))
    if not address or address != _text(b.get("address")):
        return False
    name_a, name_b = _text(a["name"]), _text(b["name"])
    if name_a == name_b:
        return True
    if re.sub(r"본점$", "", name_a) != re.sub(r"본점$", "", name_b):
        return False
    phone_a = re.sub(r"\D", "", a.get("phone") or "")
    phone_b = re.sub(r"\D", "", b.get("phone") or "")
    if phone_a and phone_b:
        return len(phone_a) >= 9 and phone_a == phone_b
    coords = [a.get("latitude"), a.get("longitude"), b.get("latitude"), b.get("longitude")]
    return all(c is not None for c in coords) and haversine_km(*coords) <= 0.02


def merge_meal_places(restaurants):
    groups = []
    buckets = {}
    for row in restaurants:
        key = (re.sub(r"본점$", "", _text(row["name"])), _text(row.get("address")))
        group = next((g for g in buckets.get(key, []) if _same_place(g, row)), None)
        if group is None:
            group = {**row, "menu": list(row["menu"]), "broadcasts": list(row["broadcasts"])}
            groups.append(group)
            buckets.setdefault(key, []).append(group)
        else:
            # Union before filtering, so an excluded broadcast on a duplicate
            # record cannot re-enter through another ID.
            group["broadcasts"] = list(dict.fromkeys(group["broadcasts"] + row["broadcasts"]))
            group["menu"].extend(row["menu"])
    return groups

"""같은 가게를 가리키는 행을 알아보는 규칙 — 크롤러와 중복 병합 스크립트가 함께 쓴다.

matzipmap은 한 가게를 방송마다 별도의 /place/<uuid> 페이지로 올리기도 한다 (일미장어: 백반기행·백년가게).
두 페이지는 이름·좌표·전화가 같고 서로를 가리키는 외부 장소 ID도 없어서, uuid를 그대로 행 id로 쓰면
같은 가게가 두 행이 된다. 그래서 정규화한 이름이 같고 SAME_PLACE_M 안에 있으면 같은 가게로 본다.
전화번호까지 같으면 SAME_PLACE_WITH_PHONE_M까지 본다 — 한쪽은 지번, 한쪽은 도로명 주소로 찍혀
좌표가 수십 m 어긋난 경우가 있다 (진미식당 문배동 33-3 / 백범로90길 38, 46m).
이름만 같은 다른 지점(진미식당 용산·마포)은 좌표가 멀어 합쳐지지 않고, 이름만으로는 절대 합치지 않는다.
"""
import re
from types import SimpleNamespace

from sqlalchemy import select

from app.geo import bounding_box_with_margin, haversine_km
from app.models import Restaurant

SAME_PLACE_M = 30
SAME_PLACE_WITH_PHONE_M = 150


def name_key(name: str | None) -> str:
    return re.sub(r"\s+|\(주\)|주식회사|본점$", "", (name or "").strip()).casefold()


def phone_key(phone: str | None) -> str:
    return re.sub(r"\D", "", phone or "")


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return haversine_km(lat1, lng1, lat2, lng2) * 1000


def is_same_place(a, b) -> bool:
    """a, b: name·latitude·longitude·phone을 가진 객체 (Restaurant 행 등)."""
    key = name_key(a.name)
    if not key or key != name_key(b.name) or None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return False
    distance = distance_m(a.latitude, a.longitude, b.latitude, b.longitude)
    return distance <= SAME_PLACE_M or (
        distance <= SAME_PLACE_WITH_PHONE_M and bool(phone_key(a.phone)) and phone_key(a.phone) == phone_key(b.phone)
    )


def find_same_place(session, *, name: str | None, latitude: float, longitude: float,
                    phone: str | None = None) -> Restaurant | None:
    """이미 DB에 있는 같은 가게 중 가장 가까운 행. 없으면 None."""
    place = SimpleNamespace(name=name, latitude=latitude, longitude=longitude, phone=phone)
    if not name_key(name):
        return None
    min_lat, max_lat, min_lng, max_lng = bounding_box_with_margin(
        [{"lat": latitude, "lng": longitude}], SAME_PLACE_WITH_PHONE_M / 1000
    )
    nearby = session.scalars(select(Restaurant).where(
        Restaurant.latitude.between(min_lat, max_lat), Restaurant.longitude.between(min_lng, max_lng),
    ))
    matches = [
        (distance_m(latitude, longitude, r.latitude, r.longitude), r.id, r)
        for r in nearby if is_same_place(place, r)
    ]
    return min(matches)[2] if matches else None

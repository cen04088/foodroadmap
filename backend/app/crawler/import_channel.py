"""matzipmap에 없는 유튜브 채널 맛집을 정리된 JSON(data/channels/*.json)으로 들여온다.

python -m app.crawler.import_channel data/channels/dudley.json [--write]

이미 다른 방송으로 들어와 있는 가게(근처 150m + 이름 포함 관계)는 새로 만들지 않고 방송 태그만
붙인다 — 같은 가게가 두 번 뜨지 않게. --write 없이 실행하면 결과만 보여주고 롤백한다.
다시 실행해도 같은 source_id는 같은 행을 갱신하므로 중복이 생기지 않는다.
"""
import argparse
import json
import os
import re
from pathlib import Path

from sqlalchemy import select

from app.crawler.run_crawl import upsert_broadcast, upsert_restaurant
from app.db import init_db, make_engine, make_session_factory
from app.geo import haversine_km
from app.models import Restaurant

SAME_PLACE_KM = 0.15


def _name_key(name: str) -> str:
    return re.sub(r"\s+|\(주\)|주식회사|본점$", "", name or "").casefold()


def _restaurant_id(slug: str, source_id: str) -> str:
    return f"{slug}:{source_id}"


def find_existing(candidates: list[Restaurant], row: dict) -> Restaurant | None:
    key = _name_key(row["name"])
    best = None
    for r in candidates:
        if r.latitude is None:
            continue
        distance = haversine_km(row["latitude"], row["longitude"], r.latitude, r.longitude)
        other = _name_key(r.name)
        if distance <= SAME_PLACE_KM and key and other and (key in other or other in key):
            if best is None or distance < best[0]:
                best = (distance, r)
    return best[1] if best else None


def import_channel(session, data: dict, write: bool = False) -> dict:
    slug, name = data["slug"], data["name"]
    broadcast = upsert_broadcast(session, slug, name)
    prefix = f"{slug}:"
    others = [r for r in session.scalars(select(Restaurant).where(Restaurant.latitude.is_not(None)))
              if not r.id.startswith(prefix)]
    report = {"created": [], "updated": [], "tagged_existing": []}
    try:
        for row in data["restaurants"]:
            rid = _restaurant_id(slug, row["source_id"])
            restaurant = session.get(Restaurant, rid)
            if restaurant is None:
                existing = find_existing(others, row)
                if existing is not None:
                    if broadcast not in existing.broadcasts:
                        existing.broadcasts.append(broadcast)
                    report["tagged_existing"].append((row["name"], existing.id, existing.name))
                    continue
                report["created"].append(row["name"])
            else:
                report["updated"].append(row["name"])
            restaurant = upsert_restaurant(session, {
                "external_id": rid, "name": row["name"], "category": row.get("category"),
                "address": row.get("address"), "phone": row.get("phone"), "hours": row.get("hours"),
                "latitude": row["latitude"], "longitude": row["longitude"],
                "youtube_url": row.get("youtube_url"), "menu": row.get("menu"),
            })
            if broadcast not in restaurant.broadcasts:
                restaurant.broadcasts.append(broadcast)
        session.flush()
        if write:
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file")
    parser.add_argument("--write", action="store_true", help="DB에 반영한다 (없으면 확인만 하고 롤백)")
    args = parser.parse_args()
    # railway ssh 셸에는 서버의 환경변수가 없다. 그대로 실행하면 기본값인 로컬 sqlite 파일에
    # 조용히 써버리고 운영 DB는 그대로라, 대상 DB를 명시하지 않으면 멈춘다.
    if not os.environ.get("DATABASE_URL"):
        parser.error("DATABASE_URL이 설정되지 않았습니다 — 대상 DB를 명시해서 실행하세요")
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    engine = make_engine()
    try:
        init_db(engine)
        with make_session_factory(engine)() as session:
            report = import_channel(session, data, write=args.write)
    finally:
        engine.dispose()
    print(f"[{data['name']}] {'반영' if args.write else '미리보기(롤백)'}: "
          f"신규 {len(report['created'])}, 갱신 {len(report['updated'])}, 기존 가게에 태그 {len(report['tagged_existing'])}")
    for name, rid, existing in report["tagged_existing"]:
        print(f"  태그: {name} -> {existing} ({rid})")


if __name__ == "__main__":
    main()

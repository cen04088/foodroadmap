"""같은 가게가 방송마다 다른 행으로 들어가 생긴 중복을 한 행으로 합친다 (일회성).

python -m app.crawler.merge_duplicates [--apply]

정규화한 이름이 같고 30m 안(전화번호도 같으면 150m 안)에 있는 행들을 한 가게로 보고 (app.crawler.dedup), 데이터가 가장 많은 행
(메뉴·영업시간·전화·영상 등)을 남긴다. 나머지 행의 방송 태그와 남는 행에 없는 메뉴, 메뉴 검토 기록을
남는 행으로 옮기고, 남는 행의 빈 칸을 채운 뒤 지운다. 저장된 AI 추천 경로 컨텍스트 안의 id도 남는 행으로
바꾼다. --apply 없이 실행하면 같은 병합을 트랜잭션 안에서 해보고 결과만 보여준 뒤 롤백한다.
다시 실행해도 합칠 묶음이 없으면 아무것도 바꾸지 않는다.
"""
import argparse
import json
import os
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.crawler.dedup import is_same_place, name_key
from app.db import init_db, make_engine, make_session_factory
from app.models import MealRouteContext, MenuAssessment, MenuItem, Restaurant, restaurant_broadcasts

FILLABLE_FIELDS = ("category", "address", "phone", "hours", "youtube_url")
ASSESSMENT_FIELDS = ("kind", "standalone", "status", "source", "evidence", "reviewed_by", "updated_at")


def find_duplicate_groups(restaurants: list[Restaurant]) -> list[list[Restaurant]]:
    by_name = defaultdict(list)
    for r in restaurants:
        if name_key(r.name) and r.latitude is not None and r.longitude is not None:
            by_name[name_key(r.name)].append(r)

    groups = []
    for rows in by_name.values():
        rows.sort(key=lambda r: r.id)
        parent = list(range(len(rows)))

        def root(i):
            while parent[i] != i:
                i = parent[i]
            return i

        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if is_same_place(rows[i], rows[j]):
                    parent[root(j)] = root(i)
        clusters = defaultdict(list)
        for i, r in enumerate(rows):
            clusters[root(i)].append(r)
        groups.extend(c for c in clusters.values() if len(c) > 1)
    return sorted(groups, key=lambda g: (g[0].name, g[0].id))


def richness(r: Restaurant) -> tuple:
    filled = sum(bool(v) for v in (r.menu_items, r.hours, r.phone, r.youtube_url, r.address, r.category))
    return filled, len(r.menu_items), len(r.hours or "")


def pick_keeper(group: list[Restaurant]) -> Restaurant:
    # 동점이면 id 순 — 다시 실행하거나 미리보기와 실제 반영에서 같은 행이 남도록.
    return min(group, key=lambda r: (tuple(-x for x in richness(r)), r.id))


def _merge_assessments(session, keep: Restaurant, drop: Restaurant) -> int:
    moved = 0
    for src in session.scalars(select(MenuAssessment).where(MenuAssessment.restaurant_id == drop.id)).all():
        dst = session.get(MenuAssessment, (keep.id, src.menu_name))
        if dst is None:
            session.add(MenuAssessment(restaurant_id=keep.id, menu_name=src.menu_name,
                                       **{f: getattr(src, f) for f in ASSESSMENT_FIELDS}))
            moved += 1
        elif dst.status != "verified" and src.status == "verified":
            # 사람이 검토한 기록이 이름 규칙 제안보다 낫다.
            for f in ASSESSMENT_FIELDS:
                setattr(dst, f, getattr(src, f))
            moved += 1
        session.delete(src)
        session.flush()
    return moved


def _rewrite_contexts(session, id_map: dict[str, str]) -> int:
    """30분짜리 AI 추천 컨텍스트 안에 지울 id가 있으면 남는 id로 바꾼다 (둘 다 있으면 하나만 남긴다)."""
    rewritten = 0
    for context in session.scalars(select(MealRouteContext)):
        entries = json.loads(context.payload)
        if not any(e.get("id") in id_map for e in entries):
            continue
        seen, kept = set(), []
        for e in entries:
            rid = id_map.get(e.get("id"), e.get("id"))
            if rid not in seen:
                seen.add(rid)
                kept.append({**e, "id": rid})
        context.payload = json.dumps(kept, ensure_ascii=False)
        rewritten += 1
    return rewritten


def remaining_references(session, ids: list[str]) -> dict[str, int]:
    counts = {
        "restaurants": session.scalar(select(func.count()).where(Restaurant.id.in_(ids))),
        "restaurant_broadcasts": session.scalar(
            select(func.count()).where(restaurant_broadcasts.c.restaurant_id.in_(ids))),
        "menu_items": session.scalar(select(func.count()).where(MenuItem.restaurant_id.in_(ids))),
        "menu_assessments": session.scalar(select(func.count()).where(MenuAssessment.restaurant_id.in_(ids))),
        "meal_route_contexts": sum(
            any(e.get("id") in ids for e in json.loads(payload))
            for payload in session.scalars(select(MealRouteContext.payload))
        ),
    }
    return {table: n for table, n in counts.items() if n}


def merge_group(session, group: list[Restaurant]) -> dict:
    keep = pick_keeper(group)
    drops = [r for r in group if r is not keep]
    report = {
        "keep": (keep.id, keep.name, [b.name for b in keep.broadcasts], len(keep.menu_items)),
        "drop": [(r.id, [b.name for b in r.broadcasts], len(r.menu_items)) for r in drops],
        "filled": [], "menu_moved": [], "assessments_moved": 0,
    }
    for drop in drops:
        for broadcast in list(drop.broadcasts):
            if broadcast not in keep.broadcasts:
                keep.broadcasts.append(broadcast)
        drop.broadcasts.clear()

        for field in FILLABLE_FIELDS:
            if not getattr(keep, field) and getattr(drop, field):
                setattr(keep, field, getattr(drop, field))
                report["filled"].append(field)

        # 같은 이름의 메뉴는 남는 행의 것을 쓴다 — 두 페이지의 메뉴판은 대개 같아서 그대로 합치면 두 번씩 뜬다.
        names = {m.name for m in keep.menu_items}
        position = max((m.position for m in keep.menu_items), default=-1) + 1
        for item in list(drop.menu_items):
            if item.name in names:
                continue
            names.add(item.name)
            item.position = position
            position += 1
            keep.menu_items.append(item)
            report["menu_moved"].append(item.name)
        session.flush()

        report["assessments_moved"] += _merge_assessments(session, keep, drop)
        session.delete(drop)
    session.flush()
    report["broadcasts_after"] = [b.name for b in keep.broadcasts]
    return report


def merge_duplicates(session, apply: bool = False) -> dict:
    restaurants = list(session.scalars(
        select(Restaurant)
        .options(selectinload(Restaurant.broadcasts), selectinload(Restaurant.menu_items))
        .order_by(Restaurant.id)
    ))
    try:
        groups = find_duplicate_groups(restaurants)
        merges = [merge_group(session, g) for g in groups]
        id_map = {rid: m["keep"][0] for m in merges for rid, _, _ in m["drop"]}
        contexts = _rewrite_contexts(session, id_map)
        session.flush()
        leftovers = remaining_references(session, list(id_map))
        if leftovers:
            raise RuntimeError(f"지운 id를 아직 참조하는 행이 있습니다: {leftovers}")
        if apply:
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    return {"merges": merges, "contexts_rewritten": contexts}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="DB에 반영한다 (없으면 확인만 하고 롤백)")
    args = parser.parse_args()
    # import_channel과 같은 이유 — railway ssh 셸에는 서버의 환경변수가 없어서, 그대로 실행하면
    # 기본값인 로컬 sqlite 파일을 대상으로 돌고 운영 DB는 그대로다.
    if not os.environ.get("DATABASE_URL"):
        parser.error("DATABASE_URL이 설정되지 않았습니다 — 대상 DB를 명시해서 실행하세요")
    engine = make_engine()
    try:
        init_db(engine)
        with make_session_factory(engine)() as session:
            result = merge_duplicates(session, apply=args.apply)
    finally:
        engine.dispose()

    merges = result["merges"]
    print(f"{'반영' if args.apply else '미리보기(롤백)'}: 중복 묶음 {len(merges)}개, "
          f"지울 행 {sum(len(m['drop']) for m in merges)}개, AI 컨텍스트 갱신 {result['contexts_rewritten']}개")
    for m in merges:
        keep_id, name, keep_broadcasts, keep_menu = m["keep"]
        print(f"- {name}: 남김 {keep_id} (방송 {keep_broadcasts}, 메뉴 {keep_menu}개)")
        for drop_id, broadcasts, menu in m["drop"]:
            print(f"    지움 {drop_id} (방송 {broadcasts}, 메뉴 {menu}개)")
        print(f"    -> 방송 {m['broadcasts_after']}"
              + (f", 채운 칸 {m['filled']}" if m["filled"] else "")
              + (f", 옮긴 메뉴 {m['menu_moved']}" if m["menu_moved"] else "")
              + (f", 옮긴 메뉴 검토 {m['assessments_moved']}개" if m["assessments_moved"] else ""))


if __name__ == "__main__":
    main()

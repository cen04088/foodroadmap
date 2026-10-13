import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.pool import StaticPool

from app.crawler.merge_duplicates import main, merge_duplicates
from app.db import init_db, make_session_factory
from app.models import Broadcast, MealRouteContext, MenuAssessment, MenuItem, Restaurant

NOW = datetime(2026, 10, 13, 12, 0)


def _enforce_foreign_keys(engine):
    # 운영 Postgres처럼 FK를 검사해야 지우는 순서가 틀렸을 때 테스트가 잡아낸다 (sqlite는 기본이 꺼짐).
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    _enforce_foreign_keys(engine)
    init_db(engine)
    yield make_session_factory(engine)
    engine.dispose()


def menu(*names, representative=()):
    return [MenuItem(name=n, price_won=10000 + i, is_representative=n in representative, position=i)
            for i, n in enumerate(names)]


def assessment(restaurant_id, menu_name, status="unverified", evidence="이름 규칙"):
    return MenuAssessment(restaurant_id=restaurant_id, menu_name=menu_name, kind="meal", standalone="yes",
                          status=status, source="manual" if status == "verified" else "name_rule",
                          evidence=evidence, updated_at=NOW)


def seed_ilmi(session):
    """운영에서 본 일미장어 — 같은 이름·좌표의 두 matzipmap 페이지가 방송 하나씩 달고 들어와 있다."""
    baekban = Broadcast(id="baekban", name="허영만의 백반기행")
    centennial = Broadcast(id="centennial", name="백년가게")
    sparse = Restaurant(id="bd41d2cc", name="일미장어", category="한식", address="서울특별시 용산구 후암로57길 35-15",
                        latitude=37.5521681, longitude=126.9743381, phone=None, hours="월~금 11:30~21:00",
                        broadcasts=[baekban], menu_items=menu("장어구이", "장어탕"))
    rich = Restaurant(id="5052fb0f", name="일미장어", category="한식", address="서울특별시 용산구 후암로57길 35-15",
                      latitude=37.5521681, longitude=126.9743381, phone="02-777-4380",
                      hours="월 휴무, 화~금 11:30~21:00", youtube_url="https://www.youtube.com/watch?v=x",
                      broadcasts=[centennial], menu_items=menu("장어구이", "장어덮밥", "장어탕"))
    session.add_all([sparse, rich])
    session.flush()  # MenuAssessment has no relationship, so the FK order has to be explicit
    session.add_all([
        assessment("bd41d2cc", "장어탕", status="verified", evidence="메뉴판 사진"),
        assessment("5052fb0f", "장어탕"),
        assessment("bd41d2cc", "장어구이", status="verified", evidence="방송 화면"),
    ])
    session.add(MealRouteContext(
        id="ctx", expires_at=NOW + timedelta(minutes=30), request_count=0,
        payload=json.dumps([{"id": "bd41d2cc", "name": "일미장어"}, {"id": "5052fb0f", "name": "일미장어"},
                            {"id": "other", "name": "다른집"}], ensure_ascii=False),
    ))
    session.commit()


def test_merges_same_place_into_the_richest_row(factory):
    with factory() as session:
        seed_ilmi(session)
        result = merge_duplicates(session, apply=True)

    [merge] = result["merges"]
    assert merge["keep"][0] == "5052fb0f"
    assert [d[0] for d in merge["drop"]] == ["bd41d2cc"]
    assert result["contexts_rewritten"] == 1

    with factory() as session:
        assert session.get(Restaurant, "bd41d2cc") is None
        kept = session.get(Restaurant, "5052fb0f")
        assert {b.name for b in kept.broadcasts} == {"허영만의 백반기행", "백년가게"}
        assert kept.phone == "02-777-4380" and kept.hours == "월 휴무, 화~금 11:30~21:00"
        # 같은 이름 메뉴는 남는 행의 것 하나만, 남는 행에 없던 메뉴는 없다 — 두 행의 메뉴판이 같은 경우.
        assert [m.name for m in kept.menu_items] == ["장어구이", "장어덮밥", "장어탕"]
        assert session.query(MenuItem).count() == 3

        reviews = {a.menu_name: a for a in session.scalars(select(MenuAssessment))}
        assert {a.restaurant_id for a in reviews.values()} == {"5052fb0f"}
        # 사람이 확인한 검토가 이름 규칙 제안을 대신한다.
        assert reviews["장어탕"].status == "verified" and reviews["장어탕"].evidence == "메뉴판 사진"
        assert reviews["장어구이"].evidence == "방송 화면"

        payload = json.loads(session.get(MealRouteContext, "ctx").payload)
        assert [e["id"] for e in payload] == ["5052fb0f", "other"]


def test_moves_menu_items_and_fills_blanks_from_the_dropped_row(factory):
    with factory() as session:
        broadcast = Broadcast(id="b1", name="백반기행")
        session.add_all([
            Restaurant(id="a", name="뚱보식당", latitude=37.5618, longitude=126.9917, phone="02-2267-1801",
                       hours="월~토 11:00~22:00", broadcasts=[broadcast],
                       menu_items=menu("갈치조림", "고등어구이", "김치찌개", representative=("갈치조림",))),
            Restaurant(id="b", name="뚱보식당", latitude=37.56181, longitude=126.99171,
                       youtube_url="https://www.youtube.com/watch?v=y",
                       menu_items=menu("갈치조림", "제육볶음", representative=("제육볶음",))),
        ])
        session.commit()
        merge_duplicates(session, apply=True)

    with factory() as session:
        kept = session.get(Restaurant, "a")
        assert kept.youtube_url == "https://www.youtube.com/watch?v=y"
        assert [(m.name, m.position, m.is_representative) for m in kept.menu_items] == [
            ("갈치조림", 0, True), ("고등어구이", 1, False), ("김치찌개", 2, False), ("제육볶음", 3, True),
        ]
        assert session.get(Restaurant, "b") is None
        assert session.query(MenuItem).count() == 4


def test_dry_run_reports_the_plan_without_changing_anything(factory):
    with factory() as session:
        seed_ilmi(session)
        result = merge_duplicates(session)

    [merge] = result["merges"]
    assert merge["keep"][:2] == ("5052fb0f", "일미장어")
    assert set(merge["broadcasts_after"]) == {"허영만의 백반기행", "백년가게"}
    with factory() as session:
        assert session.query(Restaurant).count() == 2
        assert session.query(MenuItem).count() == 5
        assert session.query(MenuAssessment).count() == 3
        assert [b.name for b in session.get(Restaurant, "bd41d2cc").broadcasts] == ["허영만의 백반기행"]
        assert "bd41d2cc" in session.get(MealRouteContext, "ctx").payload


def test_rerun_is_a_no_op(factory):
    with factory() as session:
        seed_ilmi(session)
        merge_duplicates(session, apply=True)
        assert merge_duplicates(session, apply=True) == {"merges": [], "contexts_rewritten": 0}
        assert session.query(Restaurant).count() == 1


def test_branches_and_neighbours_are_not_merged(factory):
    with factory() as session:
        session.add_all([
            # 같은 이름의 다른 지점 (용산·마포, 2km 거리).
            Restaurant(id="j1", name="진미식당", latitude=37.5367409, longitude=126.9696679),
            Restaurant(id="j2", name="진미식당", latitude=37.5506119, longitude=126.9557656),
            # 같은 건물의 다른 가게.
            Restaurant(id="n1", name="일미장어", latitude=37.5521681, longitude=126.9743381),
            Restaurant(id="n2", name="일미분식", latitude=37.5521681, longitude=126.9743381),
            # 같은 이름이지만 50m 떨어져 있다.
            Restaurant(id="f1", name="용금옥", latitude=37.5676692, longitude=126.9806025),
            Restaurant(id="f2", name="용금옥", latitude=37.5681192, longitude=126.9806025),
        ])
        session.commit()
        assert merge_duplicates(session, apply=True)["merges"] == []
        assert session.query(Restaurant).count() == 6


@pytest.mark.parametrize("second_lat, second_phone, merged", [
    # 진미식당: 지번(문배동 33-3)과 도로명(백범로90길 38) 주소로 각각 찍혀 46m 어긋난 같은 가게.
    (37.5371539, "02-703-6842", True),
    (37.5371539, "0505-111-2222", False),
    (37.5371539, None, False),
    # 전화가 같아도 200m 떨어지면 다른 곳으로 둔다.
    (37.5385409, "02-703-6842", False),
])
def test_same_phone_widens_the_match_radius(factory, second_lat, second_phone, merged):
    with factory() as session:
        session.add_all([
            Restaurant(id="j1", name="진미식당", latitude=37.5367409, longitude=126.9696679, phone="02-703-6842"),
            Restaurant(id="j2", name="진미식당", latitude=second_lat, longitude=126.9696679, phone=second_phone),
        ])
        session.commit()
        merge_duplicates(session, apply=True)
        assert session.query(Restaurant).count() == (1 if merged else 2)


def test_name_variants_of_the_same_place_are_merged(factory):
    with factory() as session:
        session.add_all([
            Restaurant(id="c1", name="창성옥", latitude=37.70, longitude=128.90),
            Restaurant(id="c2", name="창성옥 본점", latitude=37.70005, longitude=128.90),
            Restaurant(id="c3", name="창성옥", latitude=None, longitude=None),
        ])
        session.commit()
        [merge] = merge_duplicates(session, apply=True)["merges"]
    assert (merge["keep"][0], [d[0] for d in merge["drop"]]) == ("c1", ["c2"])


def test_cli_refuses_to_guess_the_target_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["merge_duplicates", "--apply"])
    with pytest.raises(SystemExit):
        main()


@pytest.mark.parametrize("apply", [False, True])
def test_cli_only_writes_with_apply(tmp_path, monkeypatch, capsys, apply):
    url = f"sqlite:///{tmp_path / 'foodmap.db'}"
    engine = create_engine(url)
    init_db(engine)
    with make_session_factory(engine)() as session:
        seed_ilmi(session)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr("sys.argv", ["merge_duplicates", *(["--apply"] if apply else [])])

    main()

    out = capsys.readouterr().out
    assert "중복 묶음 1개" in out and "지움 bd41d2cc" in out
    with make_session_factory(engine)() as session:
        assert session.query(Restaurant).count() == (1 if apply else 2)
    engine.dispose()

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.crawler.import_channel import import_channel, main
from app.db import init_db, make_session_factory
from app.models import Broadcast, Restaurant

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "channels"


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(Restaurant(id="mz-1", name="나주곰탕 하얀집", latitude=35.0322, longitude=126.7171,
                               broadcasts=[Broadcast(id="baekban", name="허영만의 백반기행")]))
        session.commit()
    return factory


def channel(*rows):
    return {"slug": "yooxicman", "name": "육식맨", "restaurants": list(rows)}


def row(source_id, name, lat, lng, **extra):
    return {"source_id": source_id, "name": name, "category": "한식", "latitude": lat, "longitude": lng, **extra}


def test_existing_place_is_tagged_instead_of_duplicated(factory):
    data = channel(row("g:1", "나주곰탕 하얀집 본점", 35.03225, 126.71707),
                   row("g:2", "신식당", 35.3216, 126.9816, menu=[{"name": "떡갈비", "price_won": 30000}]))
    with factory() as session:
        report = import_channel(session, data, write=True)
    assert report["created"] == ["신식당"]
    assert [t[1] for t in report["tagged_existing"]] == ["mz-1"]
    with factory() as session:
        assert {b.name for b in session.get(Restaurant, "mz-1").broadcasts} == {"허영만의 백반기행", "육식맨"}
        created = session.get(Restaurant, "yooxicman:g:2")
        assert [b.name for b in created.broadcasts] == ["육식맨"]
        assert [m.name for m in created.menu_items] == ["떡갈비"]
        assert session.query(Restaurant).count() == 2


def test_same_name_far_away_is_a_different_place(factory):
    with factory() as session:
        report = import_channel(session, channel(row("g:1", "나주곰탕 하얀집", 37.5, 127.0)), write=True)
    assert report["created"] == ["나주곰탕 하얀집"]


def test_dry_run_rolls_back_and_rerun_is_idempotent(factory):
    data = channel(row("g:2", "신식당", 35.3216, 126.9816))
    with factory() as session:
        import_channel(session, data)
    with factory() as session:
        assert session.get(Restaurant, "yooxicman:g:2") is None
        import_channel(session, data, write=True)
    with factory() as session:
        report = import_channel(session, data, write=True)
        assert report["updated"] == ["신식당"]
        assert session.query(Restaurant).count() == 2


@pytest.mark.parametrize("name", ["dudley.json", "yooxicman.json"])
def test_bundled_channel_files_are_well_formed(name):
    data = json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
    ids = [r["source_id"] for r in data["restaurants"]]
    assert len(ids) == len(set(ids))
    for r in data["restaurants"]:
        assert r["name"] and 33 < r["latitude"] < 39 and 124 < r["longitude"] < 132
        assert r["category"] in {"한식", "중식", "일식", "양식", "카페", "술집", "아시안", "기타"}


def test_cli_refuses_to_guess_the_target_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["import_channel", str(DATA_DIR / "yooxicman.json"), "--write"])
    with pytest.raises(SystemExit):
        main()

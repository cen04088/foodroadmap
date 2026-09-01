from sqlalchemy import inspect

from app.db import make_engine, init_db, make_session_factory
from app.models import Restaurant, Broadcast


def test_init_db_creates_tables_and_roundtrips_data():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)

    table_names = set(inspect(engine).get_table_names())
    assert {"restaurants", "broadcasts", "restaurant_broadcasts"} <= table_names

    session_factory = make_session_factory(engine)
    with session_factory() as session:
        broadcast = Broadcast(id="ttoganjib", name="또간집")
        restaurant = Restaurant(
            id="baccbc42-f664-444a-8b73-951e2cf9eaa9",
            name="경양카츠 연남점",
            category="일식",
            address="서울 마포구 연남동 260-29",
            phone="070-7543-5445",
            hours="월~일 11:30~21:00",
            latitude=37.5612032,
            longitude=126.9244277,
        )
        restaurant.broadcasts.append(broadcast)
        session.add(restaurant)
        session.commit()

    with session_factory() as session:
        loaded = session.get(Restaurant, "baccbc42-f664-444a-8b73-951e2cf9eaa9")
        assert loaded.name == "경양카츠 연남점"
        assert loaded.latitude == 37.5612032
        assert [b.id for b in loaded.broadcasts] == ["ttoganjib"]

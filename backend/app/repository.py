from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Broadcast, MenuItem, Restaurant, restaurant_broadcasts


def _reference_price_column():
    """가격 필터의 기준이 되는 "이 집 한 끼 값".

    최저가 메뉴를 쓰면 공기밥·음료 때문에 거의 모든 가게가 최저 구간에 걸려 필터가
    무의미해진다. 그래서 가게가 직접 "대표"로 표시한 메뉴의 최저가를 먼저 보고,
    대표 표시가 없는 가게만 전체 메뉴 최저가로 폴백한다.
    """
    representative = (
        select(func.min(MenuItem.price_won))
        .where(
            MenuItem.restaurant_id == Restaurant.id,
            MenuItem.is_representative.is_(True),
            MenuItem.price_won.is_not(None),
        )
        .scalar_subquery()
    )
    any_menu = (
        select(func.min(MenuItem.price_won))
        .where(MenuItem.restaurant_id == Restaurant.id, MenuItem.price_won.is_not(None))
        .scalar_subquery()
    )
    return func.coalesce(representative, any_menu)


def _apply_price_filter(stmt, min_price: int | None, max_price: int | None):
    # 가격을 지정하지 않았으면 메뉴 가격이 없는 가게도 그대로 남긴다 — 필터를 걸었을
    # 때만 "가격을 아는 가게" 중에서 고른다.
    if min_price is None and max_price is None:
        return stmt
    price = _reference_price_column()
    stmt = stmt.where(price.is_not(None))
    if min_price is not None:
        stmt = stmt.where(price >= min_price)
    if max_price is not None:
        stmt = stmt.where(price <= max_price)
    return stmt


def query_candidate_restaurants(
    session: Session,
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    *,
    broadcast_slug: str | None = None,
    category: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
) -> list[Restaurant]:
    stmt = select(Restaurant).options(
        selectinload(Restaurant.broadcasts), selectinload(Restaurant.menu_items)
    ).where(
        Restaurant.latitude.is_not(None),
        Restaurant.longitude.is_not(None),
        Restaurant.latitude.between(min_lat, max_lat),
        Restaurant.longitude.between(min_lng, max_lng),
    )

    stmt = _apply_price_filter(stmt, min_price, max_price)

    if category:
        stmt = stmt.where(Restaurant.category == category)

    if broadcast_slug:
        stmt = stmt.join(Restaurant.broadcasts).where(
            or_(Broadcast.id == broadcast_slug, Broadcast.name == broadcast_slug)
        )

    return list(session.scalars(stmt).unique())


def list_all_restaurants(
    session: Session,
    *,
    broadcast_slug: str | None = None,
    category: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
) -> list[Restaurant]:
    stmt = select(Restaurant).options(
        selectinload(Restaurant.broadcasts), selectinload(Restaurant.menu_items)
    ).where(
        Restaurant.latitude.is_not(None),
        Restaurant.longitude.is_not(None),
    )

    if bbox:
        min_lat, max_lat, min_lng, max_lng = bbox
        stmt = stmt.where(
            Restaurant.latitude.between(min_lat, max_lat),
            Restaurant.longitude.between(min_lng, max_lng),
        )

    stmt = _apply_price_filter(stmt, min_price, max_price)

    if category:
        stmt = stmt.where(Restaurant.category == category)

    if broadcast_slug:
        stmt = stmt.join(Restaurant.broadcasts).where(
            or_(Broadcast.id == broadcast_slug, Broadcast.name == broadcast_slug)
        )

    return list(session.scalars(stmt).unique())


def list_broadcasts_with_counts(session: Session) -> list[dict]:
    counts_subquery = (
        select(
            restaurant_broadcasts.c.broadcast_id,
            func.count(restaurant_broadcasts.c.restaurant_id).label("count"),
        )
        .join(Restaurant, Restaurant.id == restaurant_broadcasts.c.restaurant_id)
        .where(Restaurant.latitude.is_not(None), Restaurant.longitude.is_not(None))
        .group_by(restaurant_broadcasts.c.broadcast_id)
        .subquery()
    )

    stmt = select(Broadcast.id, Broadcast.name, func.coalesce(counts_subquery.c.count, 0)).outerjoin(
        counts_subquery, counts_subquery.c.broadcast_id == Broadcast.id
    )

    return [
        {"slug": slug, "name": name, "count": count} for slug, name, count in session.execute(stmt)
    ]

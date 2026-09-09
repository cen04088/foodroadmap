from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Broadcast, Restaurant, restaurant_broadcasts


def query_candidate_restaurants(
    session: Session,
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    *,
    broadcast_slug: str | None = None,
    category: str | None = None,
) -> list[Restaurant]:
    stmt = select(Restaurant).options(
        selectinload(Restaurant.broadcasts), selectinload(Restaurant.menu_items)
    ).where(
        Restaurant.latitude.is_not(None),
        Restaurant.longitude.is_not(None),
        Restaurant.latitude.between(min_lat, max_lat),
        Restaurant.longitude.between(min_lng, max_lng),
    )

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

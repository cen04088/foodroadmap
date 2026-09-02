from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Broadcast, Restaurant


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
    stmt = select(Restaurant).options(selectinload(Restaurant.broadcasts)).where(
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

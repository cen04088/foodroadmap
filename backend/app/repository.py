from datetime import datetime

from sqlalchemy import func, not_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Broadcast, Restaurant, Suggestion, restaurant_broadcasts

# 서비스에서 숨기는 방송. 표본이 너무 적어(동네한바퀴 6곳) 필터로서 의미가 없는 방송은
# 조회 단계에서 걸러낸다 — DB 행은 지우지 않으므로 표본이 늘면 여기서 빼기만 하면 되돌아온다.
# 슬러그와 표시명을 둘 다 받는 이유: 크롤러는 슬러그로, 응답과 필터는 표시명으로 방송을 가리킨다.
# 크롤러의 EXCLUDED_BROADCAST_*와 짝이다 (재크롤링해도 다시 들어오지 않게).
HIDDEN_BROADCAST_KEYS: frozenset[str] = frozenset({"kimyoungchul", "동네한바퀴"})


def is_hidden_broadcast(broadcast: Broadcast) -> bool:
    return broadcast.id in HIDDEN_BROADCAST_KEYS or broadcast.name in HIDDEN_BROADCAST_KEYS


def visible_broadcast_names(restaurant: Restaurant) -> list[str]:
    """응답에 실을 방송명 — 숨긴 방송 태그는 뺀다."""
    return [b.name for b in restaurant.broadcasts if not is_hidden_broadcast(b)]


def _hidden_broadcast_clause():
    return or_(Broadcast.id.in_(HIDDEN_BROADCAST_KEYS), Broadcast.name.in_(HIDDEN_BROADCAST_KEYS))


def _without_hidden_only_restaurants(stmt):
    """숨긴 방송에만 출연한 식당을 제외한다. 다른 방송에도 나온 식당은 태그만 빼고 남긴다.

    correlate(None): 바깥 쿼리가 broadcast 필터로 같은 테이블을 join하고 있어도 서브쿼리를
    자동 상관시키지 않는다 — 상관되면 서브쿼리의 FROM이 사라져 엉뚱한 결과가 나온다.
    """
    linked = select(restaurant_broadcasts.c.restaurant_id).join(
        Broadcast, Broadcast.id == restaurant_broadcasts.c.broadcast_id
    )
    hidden_ids = linked.where(_hidden_broadcast_clause()).correlate(None)
    visible_ids = linked.where(not_(_hidden_broadcast_clause())).correlate(None)
    return stmt.where(or_(Restaurant.id.not_in(hidden_ids), Restaurant.id.in_(visible_ids)))


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
        if broadcast_slug in HIDDEN_BROADCAST_KEYS:
            return []
        stmt = stmt.join(Restaurant.broadcasts).where(
            or_(Broadcast.id == broadcast_slug, Broadcast.name == broadcast_slug)
        )

    stmt = _without_hidden_only_restaurants(stmt)
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
        if broadcast_slug in HIDDEN_BROADCAST_KEYS:
            return []
        stmt = stmt.join(Restaurant.broadcasts).where(
            or_(Broadcast.id == broadcast_slug, Broadcast.name == broadcast_slug)
        )

    stmt = _without_hidden_only_restaurants(stmt)
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

    stmt = (
        select(Broadcast.id, Broadcast.name, func.coalesce(counts_subquery.c.count, 0))
        .outerjoin(counts_subquery, counts_subquery.c.broadcast_id == Broadcast.id)
        .where(not_(_hidden_broadcast_clause()))
    )

    return [
        {"slug": slug, "name": name, "count": count} for slug, name, count in session.execute(stmt)
    ]


def create_suggestion(
    session: Session,
    *,
    kind: str,
    body: str,
    contact: str | None,
    client_ip: str | None,
    created_at: datetime,
) -> Suggestion:
    suggestion = Suggestion(
        kind=kind, body=body, contact=contact, client_ip=client_ip, created_at=created_at
    )
    session.add(suggestion)
    session.commit()
    session.refresh(suggestion)
    return suggestion


def count_suggestions_from_ip_since(session: Session, client_ip: str, since: datetime) -> int:
    """레이트리밋용 — 같은 IP가 최근에 몇 건 보냈는지."""
    stmt = (
        select(func.count())
        .select_from(Suggestion)
        .where(Suggestion.client_ip == client_ip, Suggestion.created_at >= since)
    )
    return session.scalar(stmt) or 0


def list_suggestions(session: Session, *, limit: int, offset: int) -> list[Suggestion]:
    stmt = (
        select(Suggestion).order_by(Suggestion.created_at.desc(), Suggestion.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(stmt))

import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.meal_planner import PlannerError
from app.models import MealRouteContext

CONTEXT_TTL = timedelta(minutes=30)
CONTEXT_REQUEST_LIMIT = 20


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def save_context(session: Session, restaurants: list[dict]) -> str:
    now = utcnow()
    session.execute(delete(MealRouteContext).where(MealRouteContext.expires_at <= now))
    token = secrets.token_hex(24)
    session.add(MealRouteContext(
        id=token, payload=json.dumps(restaurants, ensure_ascii=False),
        expires_at=now + CONTEXT_TTL, request_count=0,
    ))
    session.commit()
    return token


def consume_context(session: Session, token: str) -> list[dict]:
    now = utcnow()
    # Atomic across workers: concurrent requests cannot bypass the per-context cap.
    result = session.execute(update(MealRouteContext).where(
        MealRouteContext.id == token,
        MealRouteContext.expires_at > now,
        MealRouteContext.request_count < CONTEXT_REQUEST_LIMIT,
    ).values(request_count=MealRouteContext.request_count + 1))
    session.commit()
    context = session.scalar(select(MealRouteContext).where(MealRouteContext.id == token))
    if not context or context.expires_at <= now:
        raise PlannerError(410, "경로 정보가 만료됐어요. 출발지와 목적지를 다시 검색해주세요.")
    if result.rowcount != 1:
        raise PlannerError(429, "이 경로의 AI 요청 횟수를 모두 사용했어요. 경로를 다시 검색해주세요.")
    return json.loads(context.payload)

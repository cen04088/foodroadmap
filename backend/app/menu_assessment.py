"""Menu-name suggestions never become verified facts without a review."""
import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import MenuAssessment

KINDS = {"meal", "snack", "extra", "drink", "unknown"}
STANDALONE = {"yes", "no", "unknown"}


def suggest_assessment(name: str) -> dict:
    normalized = re.sub(r"\s+", "", name).casefold()
    kind = "unknown"
    if re.search(r"^(?:생맥주|병맥주|맥주|소주|하이볼|콜라|사이다|아메리카노|라떼)(?:$|[0-9(（,，/])", normalized):
        kind = "drink"
    elif re.search(r"^(?:맛계란|후라이|계란후라이|공기밥|공깃밥|곱배기|곱빼기|마무리볶음밥)(?:$|[0-9(（])|사리|추가|후식"
                   r"|^(?:오이|죽순|짜사이|자차이|단무지|김치|깍두기)(?:무침|샐러드|볶음)?$", normalized):
        kind = "extra"
    elif re.search(r"도넛|도너츠|꽈배기|쥐포|^고구마$|^알쌈$", normalized):
        kind = "snack"
    elif re.search(r"국수|냉면|국밥|해장국|덮밥|돈까스|돈가스|파스타|비빔밥|정식|떡국|짬뽕", normalized):
        kind = "meal"
    return {"kind": kind, "standalone": "unknown", "status": "unverified",
            "source": "name_rule", "evidence": f"메뉴명 기반 분류 제안: {name}"}


def assessment_dict(row: MenuAssessment) -> dict:
    return {key: getattr(row, key) for key in ("kind", "standalone", "status", "source", "evidence")}


def load_assessments(session, restaurant_ids: list[str]) -> dict:
    result = {}
    # Keep SQLite parameter counts bounded for large routes as well.
    for start in range(0, len(restaurant_ids), 400):
        for row in session.scalars(select(MenuAssessment).where(MenuAssessment.restaurant_id.in_(restaurant_ids[start:start + 400]))):
            result[(row.restaurant_id, row.menu_name)] = assessment_dict(row)
    return result


def is_verified(assessment: dict) -> bool:
    return (assessment.get("status") == "verified" and assessment.get("source") in {"manual", "source"}
            and bool(assessment.get("evidence", "").strip()))


def attach_assessments(restaurants: list[dict], assessments: dict) -> list[dict]:
    return [{**r, "menu": [{**m, "assessment": assessments.get((r["id"], m["name"]), suggest_assessment(m["name"]))}
                            for m in r["menu"]]} for r in restaurants]


def review_menu(session, *, restaurant_id: str, menu_name: str, kind: str,
                standalone: str, source: str, evidence: str, reviewer: str) -> None:
    from app.models import MenuItem
    if kind not in KINDS or standalone not in STANDALONE or source not in {"manual", "source"}:
        raise ValueError("Invalid classification or review source")
    if not evidence.strip() or not reviewer.strip():
        raise ValueError("A reviewer and source evidence are required")
    exists = session.scalar(select(MenuItem.id).where(MenuItem.restaurant_id == restaurant_id, MenuItem.name == menu_name).limit(1))
    if exists is None:
        raise ValueError("Menu no longer exists; export current menus before reviewing")
    row = session.get(MenuAssessment, (restaurant_id, menu_name))
    if row is None:
        row = MenuAssessment(restaurant_id=restaurant_id, menu_name=menu_name)
        session.add(row)
    row.kind, row.standalone, row.source = kind, standalone, source
    row.status = "unverified" if kind == "unknown" else "verified"
    row.evidence, row.reviewed_by = evidence.strip(), reviewer.strip()
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

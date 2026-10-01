"""Export classifications for review; import only explicit, evidenced approvals.

python -m app.review_menus export --file menus.json
python -m app.review_menus apply --file reviewed.json [--write]
"""
import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.db import init_db, make_engine, make_session_factory
from app.menu_assessment import load_assessments, review_menu, suggest_assessment
from app.models import MenuItem, Restaurant


def export_reviews(session, restaurant_id=None):
    stmt = select(MenuItem, Restaurant).join(Restaurant, MenuItem.restaurant_id == Restaurant.id)
    if restaurant_id:
        stmt = stmt.where(Restaurant.id == restaurant_id)
    pairs = session.execute(stmt.order_by(Restaurant.id, MenuItem.position)).all()
    existing = load_assessments(session, list({r.id for _, r in pairs}))
    return [{"restaurant_id": r.id, "restaurant_name": r.name, "address": r.address,
             "menu_name": m.name, "price_won": m.price_won,
             "source_url": f"https://www.matzipmap.com/place/{r.id}",
             "suggestion": existing.get((r.id, m.name), suggest_assessment(m.name)),
             "approve": False, "kind": "unknown", "standalone": "unknown",
             "source": "manual", "evidence": "", "reviewer": ""} for m, r in pairs]


def apply_reviews(session, rows, write=False):
    if not isinstance(rows, list):
        raise ValueError("Review file must contain a JSON array")
    seen = set()
    count = 0
    try:
        for row in rows:
            if row.get("approve") is not True:
                continue
            key = (row["restaurant_id"], row["menu_name"])
            if key in seen:
                raise ValueError("Duplicate menu review")
            seen.add(key)
            review_menu(session, **{key: row[key] for key in (
                "restaurant_id", "menu_name", "kind", "standalone", "source", "evidence", "reviewer")})
            count += 1
        session.flush()
        if write:
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["export", "apply"])
    parser.add_argument("--file", required=True)
    parser.add_argument("--restaurant-id")
    parser.add_argument("--write", action="store_true", help="Commit approved rows; otherwise validate and roll back")
    args = parser.parse_args()
    engine = make_engine()
    try:
        init_db(engine)
        with make_session_factory(engine)() as session:
            if args.command == "export":
                rows = export_reviews(session, args.restaurant_id)
                Path(args.file).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Exported {len(rows)} menus; suggestions are NOT approvals")
            else:
                rows = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
                count = apply_reviews(session, rows, args.write)
                print(f"{'Saved' if args.write else 'Validated only'} {count} reviews")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

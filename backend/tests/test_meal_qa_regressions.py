"""2026-09-30 배포 QA에서 나온 회귀 — 검토 전 메뉴, 보류 응답 탈출, 경로 밖 시간."""
import pytest

from app.meal_planner import _accept_hold_answer, recommend_meal
from app.menu_assessment import suggest_assessment
from tests.test_meal_planner import ids, preferences, restaurant


def unreviewed(id, name, price, minutes=60):
    """운영 DB처럼 검토 기록이 없어 이름 규칙 제안만 붙은 메뉴."""
    row = restaurant(id, minutes=minutes, menu=[{"name": name, "price_won": price}])
    row["menu"][0]["assessment"] = suggest_assessment(name)
    return row


def test_unreviewed_meals_are_still_recommended_without_reviews():
    rows = [unreviewed("stew", "돼지고기김치찜", 10000), unreviewed("noodle", "멸치국수", 6000)]
    result = recommend_meal(rows, preferences(sort="price"))
    assert ids(result) == ["noodle", "stew"]
    assert "메뉴 분류·단독 주문 가능 여부 미확인" in result["recommendations"][0]["reasons"]


@pytest.mark.parametrize("name,price", [
    ("콜라, 사이다", 2000), ("맛계란", 1500), ("마라탕100g", 1650), ("죽순", 1900),
    ("고구마", 700), ("오이 샐러드", 9000), ("볶음밥", 3000), ("쏘세지", 3000), ("닭꼬치", 3000),
])
def test_unreviewed_non_meals_do_not_win_a_cheap_meal_request(name, price):
    rows = [unreviewed("side", name, price), unreviewed("meal", "김밥", 3000)]
    assert ids(recommend_meal(rows, preferences(sort="price"))) == ["meal"]


def test_explicit_dish_search_still_finds_unit_priced_menu():
    rows = [unreviewed("mala", "마라탕100g", 1650)]
    assert ids(recommend_meal(rows, preferences(menu_keywords=["마라탕"]))) == ["mala"]


def test_unreviewed_drinks_remain_available_for_snack_requests():
    rows = [unreviewed("cafe", "아메리카노", 4700)]
    assert ids(recommend_meal(rows, preferences(purpose="snack"))) == ["cafe"]


HOLD = "반드시 필요한 조건(땅콩 알레르기 안전)을 확인할 수 없어 추천을 보류했어요."


def held(**changes):
    base = {"unverified": ["땅콩 알레르기 안전"], "required_unverified": ["땅콩 알레르기 안전"], "clarification": HOLD}
    return preferences(**{**base, **changes})


def test_answering_a_hold_with_search_conditions_proceeds_but_keeps_disclosure():
    parsed = held(max_price_won=20000, clarification=None)
    _accept_hold_answer(held(), parsed)
    assert parsed.required_unverified == []
    assert parsed.unverified == ["땅콩 알레르기 안전"]
    assert ids(recommend_meal([restaurant()], parsed)) == ["a"]


@pytest.mark.parametrize("parsed", [
    held(),  # 검색 조건이 그대로면 동의로 보지 않는다.
    held(max_price_won=20000, required_unverified=["땅콩 알레르기 안전", "주차 가능"]),  # 새 필수 조건
])
def test_hold_is_kept_without_new_search_conditions_or_with_new_requirements(parsed):
    before = list(parsed.required_unverified)
    _accept_hold_answer(held(), parsed)
    assert parsed.required_unverified == before


def test_time_beyond_the_route_explains_where_the_route_ends():
    rows = [restaurant("a", minutes=60), restaurant("b", minutes=190)]
    result = recommend_meal(rows, preferences(min_minutes=300))
    assert result["recommendations"] == []
    assert "출발 후 약 190분 안에" in result["reply"]

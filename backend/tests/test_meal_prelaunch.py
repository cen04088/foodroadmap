import pytest

from app.meal_planner import recommend_meal
from tests.test_meal_planner import restaurant, preferences, ids


@pytest.mark.parametrize("bounds,expected", [
    ({"min_minutes": 0, "max_minutes": 20}, ["0", "20"]),
    ({"min_minutes": 120}, ["120", "200"]),
    ({"min_minutes": 20, "max_minutes": 120}, ["33.6", "108", "120"]),
])
def test_explicit_time_bounds_override_old_symmetric_window(bounds, expected):
    rows = [restaurant(str(t), minutes=t) for t in [0, 20, 33.6, 108, 120, 200]]
    result = recommend_meal(rows, preferences(target_minutes=20, time_window_minutes=30, **bounds))
    assert ids(result) == expected


def test_reversed_time_bounds_ask_instead_of_recommending():
    result = recommend_meal([restaurant()], preferences(min_minutes=120, max_minutes=20))
    assert result["preferences"]["clarification"]
    assert not ids(result)


@pytest.mark.parametrize("exclusive,expected", [(True, ["9999"]), (False, ["9999", "10000"])])
def test_budget_comparison_preserves_exclusive_boundary(exclusive, expected):
    rows = [restaurant(str(n), price=n) for n in [9999, 10000, 10001]]
    assert ids(recommend_meal(rows, preferences(max_price_won=10000, price_exclusive=exclusive, sort="price"))) == expected


@pytest.mark.parametrize("name", ["곱배기", "곱빼기", "마무리볶음밥", "쥐포", "부산어묵 1개", "튀김(개당)", "찹쌀꽈배기 1개", "알쌈"])
def test_small_sides_do_not_become_a_meal_even_without_budget(name):
    rows = [restaurant("side", menu=[{"name": name, "price_won": 600}]), restaurant("meal")]
    assert ids(recommend_meal(rows, preferences(sort="price"))) == ["meal"]


def test_snack_and_explicit_dish_requests_still_work():
    rows = [restaurant(menu=[{"name": "쥐포", "price_won": 600}])]
    assert ids(recommend_meal(rows, preferences(purpose="snack"))) == ["a"]
    assert ids(recommend_meal(rows, preferences(menu_keywords=["쥐포"]))) == ["a"]


def test_one_explicit_extra_does_not_enable_other_extras():
    rows = [restaurant(menu=[{"name": "국수사리", "price_won": 500}, {"name": "계란", "price_won": 500}])]
    assert not ids(recommend_meal(rows, preferences(menu_keywords=["국수", "공기밥"])))


def test_representative_menu_preferred_but_price_sort_remains_cheapest():
    row = restaurant(menu=[{"name": "만두", "price_won": 6000}, {"name": "칼국수", "price_won": 10000, "is_representative": True}])
    assert recommend_meal([row], preferences())["recommendations"][0]["menu"]["name"] == "칼국수"
    assert recommend_meal([row], preferences(sort="price"))["recommendations"][0]["menu"]["name"] == "만두"


def test_all_menu_conditions_each_have_affordable_evidence():
    one = restaurant("one", menu=[{"name": "냉면", "price_won": 7000}])
    both = restaurant("both", menu=[{"name": "냉면", "price_won": 7000}, {"name": "돈까스", "price_won": 9000}])
    expensive = restaurant("expensive", menu=[{"name": "냉면", "price_won": 7000}, {"name": "돈까스", "price_won": 12000}])
    p = preferences(menu_keywords=["돈까스", "냉면"], menu_match="all", max_price_won=10000)
    result = recommend_meal([one, both, expensive], p)
    assert ids(result) == ["both"]
    assert "돈까스, 냉면" in result["recommendations"][0]["reasons"][-1]
    assert len(ids(recommend_meal([one, both, expensive], p.model_copy(update={"menu_match": "any"})))) == 3


def test_all_alias_groups_are_separate_requirements():
    row = restaurant(menu=[{"name": "삼겹살", "price_won": 17000}, {"name": "잔치국수", "price_won": 7000}])
    assert ids(recommend_meal([row], preferences(menu_keywords=["돼지고기", "면"], menu_match="all"))) == ["a"]


@pytest.mark.parametrize("condition", ["땅콩 알레르기 안전", "주차 가능"])
def test_required_unverified_stops_recommendations_and_is_disclosed(condition):
    p = preferences(categories=["한식"], required_unverified=[condition])
    result = recommend_meal([restaurant()], p)
    assert not ids(result)
    assert condition in result["preferences"]["unverified"]
    assert result["preferences"]["clarification"]
    assert p.clarification is None


def test_only_unverified_conditions_ask_for_searchable_preferences():
    result = recommend_meal([restaurant()], preferences(unverified=["영업 중", "주차 가능"]))
    assert not ids(result)
    assert result["preferences"]["clarification"]


def test_optional_unverified_and_explicit_release_allow_recommendations():
    p = preferences(menu_keywords=["국수"], unverified=["조용함"])
    assert ids(recommend_meal([restaurant()], p)) == ["a"]
    p = p.model_copy(update={"required_unverified": [], "unverified": [], "clarification": None})
    assert ids(recommend_meal([restaurant()], p)) == ["a"]


def test_excluded_broadcast_is_enforced_even_when_another_broadcast_matches():
    row = restaurant(broadcasts=["또간집", "쯔양"])
    assert not ids(recommend_meal([row], preferences(broadcasts=["쯔양"], excluded_broadcasts=["또간집"])))


def test_duplicate_known_places_do_not_take_two_slots_but_branches_remain():
    rows = [restaurant("a", address="서울 중구 1"), restaurant("b", address="서울 중구 1"), restaurant("c", address="서울 중구 2")]
    result = recommend_meal(rows, preferences())
    assert ids(result) == ["a", "c"]
    assert result["matched_count"] == 2


def test_unknown_addresses_are_not_deduplicated_by_name():
    assert len(ids(recommend_meal([restaurant("a"), restaurant("b")], preferences()))) == 2

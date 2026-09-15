"""Independent examples found while reviewing live recommendations on 2026-09-15."""
import pytest

from app.meal_planner import recommend_meal
from tests.test_meal_planner import restaurant, preferences, ids


@pytest.mark.parametrize("name", ["계란", "라면사리", "사리떡", "회 추가", "생굴(추가,계절메뉴)", "국수사리", "냉면(후식)"])
def test_add_ons_do_not_supply_meal_budget_or_price_rank(name):
    candidate = restaurant(menu=[{"name": "한우구이", "price_won": 35000}, {"name": name, "price_won": 1000}])
    assert ids(recommend_meal([candidate], preferences(max_price_won=20000, sort="price"))) == []


def test_cheap_sort_uses_meal_price_not_egg_price():
    expensive = restaurant("expensive", menu=[{"name": "계란", "price_won": 600}, {"name": "국수", "price_won": 9000}])
    affordable = restaurant("affordable", price=7000)
    assert ids(recommend_meal([expensive, affordable], preferences(sort="price"))) == ["affordable", "expensive"]


def test_noodle_request_does_not_bypass_extra_menu_exclusion():
    candidate = restaurant(menu=[{"name": "국수사리", "price_won": 1000}])
    assert ids(recommend_meal([candidate], preferences(menu_keywords=["국수"]))) == []
    assert ids(recommend_meal([candidate], preferences(menu_keywords=["국수사리"]))) == ["a"]


@pytest.mark.parametrize("word", ["회", "생선회", "횟집", "사시미"])
def test_raw_fish_search_does_not_expand_to_cooked_fish(word):
    names = ["참치김밥", "고등어구이", "고등어김치찜", "육회", "광어회", "모둠회", "회 (소)"]
    candidates = [restaurant(name, menu=[{"name": name, "price_won": 15000}]) for name in names]
    result = recommend_meal(candidates, preferences(menu_keywords=[word]))
    assert set(ids(result)) == {"광어회", "모둠회", "회 (소)"}


@pytest.mark.parametrize("name", ["생굴", "생굴(추가,계절메뉴)", "석화", "굴국밥"])
def test_seafood_exclusion_covers_oysters(name):
    candidate = restaurant(menu=[{"name": name, "price_won": 13000}])
    assert ids(recommend_meal([candidate], preferences(excluded_keywords=["해산물"]))) == []


@pytest.mark.parametrize("name", ["순대국", "닭갈비", "삼계탕", "훈제오리"])
def test_meat_group_exclusion_covers_common_meat_names(name):
    candidate = restaurant(menu=[{"name": name, "price_won": 13000}])
    assert ids(recommend_meal([candidate], preferences(excluded_keywords=["육류"]))) == []

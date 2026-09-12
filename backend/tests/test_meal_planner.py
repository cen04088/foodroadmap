import json
from unittest.mock import Mock

import pytest
import requests

from app.meal_planner import MealPreferences, PlannerError, interpret_preferences, recommend_meal


def preferences(**changes):
    return MealPreferences(**{
        "categories": [], "broadcasts": [], "menu_keywords": [], "excluded_keywords": [],
        "max_price_won": None, "target_minutes": None, "time_window_minutes": 30,
        "sort": "timing", "unverified": [], "clarification": None, **changes,
    })


def restaurant(id="a", minutes=60, price=12000, **changes):
    return {
        "id": id, "name": "테스트 국수집", "category": "한식", "broadcasts": ["또간집"],
        "cumulative_time_sec": minutes * 60, "distance_from_route_km": 0.4,
        "menu": [{"name": "잔치국수", "price_won": price, "is_representative": True}],
        **changes,
    }


def ids(result):
    return [r["restaurant_id"] for r in result["recommendations"]]


def test_time_budget_and_category_are_all_checked_and_ranked():
    candidates = [restaurant("late", 95), restaurant("b", 75), restaurant("expensive", 60, 30000),
                  restaurant("a", 55), restaurant("wrong-category", 60, category="일식")]
    result = recommend_meal(candidates, preferences(target_minutes=60, max_price_won=20000, categories=["한식"]))
    assert ids(result) == ["a", "b"]
    assert result["matched_count"] == 2
    assert "55분" in result["recommendations"][0]["reasons"][0]


@pytest.mark.parametrize("price", [None, 0, -1, 20001])
def test_unknown_or_over_budget_prices_never_pass(price):
    assert ids(recommend_meal([restaurant(price=price)], preferences(max_price_won=20000))) == []


def test_menu_and_budget_must_match_same_menu_and_all_menus_are_searched():
    menus = [{"name": "국수", "price_won": 25000}, {"name": "다른 요리", "price_won": 10000}]
    p = preferences(menu_keywords=["국수"], max_price_won=20000)
    assert ids(recommend_meal([restaurant(menu=menus)], p)) == []
    menus += [{"name": "특선", "price_won": 30000}, {"name": "잔치 국수", "price_won": 9000}]
    result = recommend_meal([restaurant(menu=menus)], p)
    assert ids(result) == ["a"]
    assert result["recommendations"][0]["menu"]["price_won"] == 9000


def test_broadcast_exclusions_and_zero_results_do_not_relax_constraints():
    assert ids(recommend_meal([restaurant()], preferences(broadcasts=["없는 방송"]))) == []
    assert ids(recommend_meal([restaurant()], preferences(excluded_keywords=["국수"]))) == []
    assert ids(recommend_meal([restaurant()], preferences(categories=["없는 업종"]))) == []


def test_cheap_drinks_or_extra_rice_do_not_qualify_a_meal_budget():
    menus = [{"name": "한우구이", "price_won": 40000}, {"name": "공기밥", "price_won": 1000}, {"name": "콜라 (병)", "price_won": 2000}]
    assert ids(recommend_meal([restaurant(menu=menus)], preferences(max_price_won=20000))) == []


def test_top_three_price_order_and_unknown_price_last():
    result = recommend_meal([restaurant(str(i), price=price) for i, price in enumerate([None, 15000, 8000, 12000, 9000])], preferences(sort="price"))
    assert ids(result) == ["2", "4", "3"]
    assert result["matched_count"] == 5


def test_unknown_conditions_are_disclosed_and_clarification_has_no_recommendations():
    result = recommend_meal([restaurant()], preferences(unverified=["주차", "영업 중"]))
    assert "주차" in " ".join(result["notes"])
    assert "주차" not in " ".join(result["recommendations"][0]["reasons"])
    result = recommend_meal([restaurant()], preferences(clarification="출발 후 몇 분쯤인가요?"))
    assert ids(result) == []


def test_deepseek_request_preserves_previous_conditions_without_sending_coordinates(monkeypatch):
    previous = preferences(target_minutes=60, max_price_won=20000)
    expected = preferences(target_minutes=30, max_price_won=20000)
    response = Mock(status_code=200)
    response.json.return_value = {"choices": [{"finish_reason": "stop", "message": {"content": expected.model_dump_json()}}]}
    post = Mock(return_value=response)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-test-key")
    monkeypatch.setattr("app.meal_planner.requests.post", post)
    assert interpret_preferences("더 일찍", previous, [restaurant(latitude=37.5, longitude=127.0)]) == expected
    args, kwargs = post.call_args
    assert args[0] == "https://api.deepseek.com/chat/completions"
    assert kwargs["json"]["response_format"] == {"type": "json_object"}
    sent = json.loads(kwargs["json"]["messages"][1]["content"])
    assert sent["previous"]["max_price_won"] == 20000
    assert "latitude" not in json.dumps(sent)
    assert "restaurant_id" not in json.dumps(sent)


@pytest.mark.parametrize("body", [
    {}, {"choices": []}, {"choices": [{"finish_reason": "length"}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": '{"restaurant_id":"invented"}'}}]},
])
def test_invalid_or_incomplete_model_output_is_not_a_recommendation(monkeypatch, body):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-test-key")
    response = Mock(status_code=200)
    response.json.return_value = body
    monkeypatch.setattr("app.meal_planner.requests.post", Mock(return_value=response))
    with pytest.raises(PlannerError) as caught:
        interpret_preferences("한식", None, [restaurant()])
    assert caught.value.status == 502


def test_missing_key_and_timeout_are_actionable(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(PlannerError) as caught:
        interpret_preferences("한식", None, [])
    assert caught.value.status == 503
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-test-key")
    monkeypatch.setattr("app.meal_planner.requests.post", Mock(side_effect=requests.Timeout))
    with pytest.raises(PlannerError) as caught:
        interpret_preferences("한식", None, [])
    assert caught.value.status == 504

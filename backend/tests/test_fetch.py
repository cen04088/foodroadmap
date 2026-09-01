from unittest.mock import patch, Mock

import pytest
import requests

from app.crawler.fetch import fetch_url


def test_fetch_url_returns_response_text_on_success():
    fake_response = Mock(text="<html>ok</html>")
    fake_response.raise_for_status = Mock()

    with patch("app.crawler.fetch.requests.get", return_value=fake_response) as mock_get:
        result = fetch_url("https://www.matzipmap.com/broadcasts")

    assert result == "<html>ok</html>"
    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == "https://www.matzipmap.com/broadcasts"


def test_fetch_url_retries_then_raises_after_exhausting_attempts():
    with patch("app.crawler.fetch.requests.get", side_effect=requests.ConnectionError("boom")) as mock_get, \
         patch("app.crawler.fetch.time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError):
            fetch_url("https://www.matzipmap.com/broadcasts", max_retries=3, backoff_seconds=0.01)

    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 3


def test_fetch_url_recovers_after_one_failed_attempt():
    fake_response = Mock(text="<html>ok</html>")
    fake_response.raise_for_status = Mock()

    with patch(
        "app.crawler.fetch.requests.get",
        side_effect=[requests.ConnectionError("boom"), fake_response],
    ) as mock_get, patch("app.crawler.fetch.time.sleep"):
        result = fetch_url("https://www.matzipmap.com/broadcasts", max_retries=3, backoff_seconds=0.01)

    assert result == "<html>ok</html>"
    assert mock_get.call_count == 2

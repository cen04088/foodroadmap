import time

import requests

USER_AGENT = "foodmap-crawler/0.1 (+contact: cen04088@gmail.com)"


def fetch_url(
    url: str,
    *,
    timeout: float = 10.0,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
) -> str:
    last_error: Exception | None = None

    for _attempt in range(max_retries):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(backoff_seconds)

    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts") from last_error

import os


class MissingKakaoApiKeyError(RuntimeError):
    pass


def get_kakao_api_key() -> str:
    api_key = os.environ.get("KAKAO_REST_API_KEY")
    if not api_key:
        raise MissingKakaoApiKeyError("KAKAO_REST_API_KEY environment variable is not set")
    return api_key

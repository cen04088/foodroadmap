import os


class MissingKakaoApiKeyError(RuntimeError):
    pass


def get_kakao_api_key() -> str:
    api_key = os.environ.get("KAKAO_REST_API_KEY")
    if not api_key:
        raise MissingKakaoApiKeyError("KAKAO_REST_API_KEY environment variable is not set")
    return api_key


class MissingAdminTokenError(RuntimeError):
    pass


def get_admin_token() -> str:
    """건의 목록 조회를 막는 토큰.

    설정하지 않으면 조회가 아예 안 되는 쪽이 안전하다 — 빈 값을 허용하면
    토큰 없이 누구나 남의 연락처까지 읽어갈 수 있다.
    """
    token = os.environ.get("ADMIN_TOKEN")
    if not token:
        raise MissingAdminTokenError("ADMIN_TOKEN environment variable is not set")
    return token

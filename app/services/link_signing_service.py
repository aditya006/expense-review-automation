from __future__ import annotations

from itsdangerous import BadData, URLSafeTimedSerializer

from app.config import get_settings

settings = get_settings()

_REVIEW_SALT = "expense-review-link"
_SPLITWISE_STATE_SALT = "splitwise-oauth-state"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.signing_secret)


def create_review_token(transaction_id: str) -> str:
    return _serializer().dumps({"tx": transaction_id, "purpose": "review"}, salt=_REVIEW_SALT)


def verify_review_token(transaction_id: str, token: str) -> bool:
    try:
        payload = _serializer().loads(
            token,
            salt=_REVIEW_SALT,
            max_age=settings.review_link_ttl_seconds,
        )
    except BadData:
        return False

    return payload.get("tx") == transaction_id and payload.get("purpose") == "review"


def build_review_link(transaction_id: str) -> str:
    token = create_review_token(transaction_id)
    base = settings.app_base_url.rstrip("/")
    return f"{base}/review/{transaction_id}?t={token}"


def create_oauth_state_token() -> str:
    return _serializer().dumps({"purpose": "splitwise_oauth"}, salt=_SPLITWISE_STATE_SALT)


def verify_oauth_state_token(token: str) -> bool:
    try:
        payload = _serializer().loads(
            token,
            salt=_SPLITWISE_STATE_SALT,
            max_age=settings.splitwise_oauth_state_ttl_seconds,
        )
    except BadData:
        return False

    return payload.get("purpose") == "splitwise_oauth"

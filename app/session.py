import base64
import hashlib
import hmac
import re
import time

SESSION_COOKIE = "inseeq_session"
MAX_AGE_SECONDS = 7 * 24 * 60 * 60
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def _sign(expires: str, password: str) -> str:
    key = hmac.new(password.encode(), b"session cookie", hashlib.sha256).digest()
    digest = hmac.new(key, expires.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(hashlib.sha256(a.encode()).digest(), hashlib.sha256(b.encode()).digest())


def create_session(password: str) -> str:
    expires = str(int(time.time()) + MAX_AGE_SECONDS)
    return f"{expires}.{_sign(expires, password)}"


def is_valid_session(session: str | None, password: str) -> bool:
    parts = (session or "").split(".")
    if len(parts) != 2 or not re.fullmatch(r"[0-9]+", parts[0]) or not parts[1]:
        return False
    expires, signature = parts
    return constant_time_equal(signature, _sign(expires, password)) and int(expires) > time.time()


def is_local(host: str | None) -> bool:
    return re.sub(r":\d+$", "", host or "") in LOCAL_HOSTS

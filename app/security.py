import hashlib
import hmac
import os

from itsdangerous import BadSignature, URLSafeTimedSerializer

from app import config

_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="lg-session")
_PBKDF_ROUNDS = 240000


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF_ROUNDS)
    return f"pbkdf2${_PBKDF_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        _, rounds, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def make_api_key():
    import secrets

    return "lg_" + secrets.token_urlsafe(32)


def hash_api_key(raw_key):
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def make_session(user_id):
    return _serializer.dumps({"uid": user_id})


def read_session(token, max_age=60 * 60 * 24 * 30):
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=max_age)
        return data.get("uid")
    except (BadSignature, Exception):
        return None

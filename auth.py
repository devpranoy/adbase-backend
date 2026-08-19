"""Auth: verify user, issue JWT, require_auth decorator."""
from datetime import datetime, timezone
from functools import wraps
from time import time
import uuid

import bcrypt
import jwt
from flask import g, request, jsonify

from config import JWT_SECRET
from supabase_client import get_client

JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "adbase-backend"
JWT_EXPIRES_SECONDS = 7 * 24 * 3600  # 7 days


def verify_user(username: str, password: str) -> str | None:
    """Return user id (uuid string) if credentials are valid, else None."""
    if not username or not password:
        return None
    client = get_client()
    r = client.table("users").select("id, password_hash").eq("username", username).limit(1).execute()
    if not r.data or len(r.data) == 0:
        return None
    row = r.data[0]
    stored_hash = row.get("password_hash")
    if not stored_hash:
        return None
    try:
        if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return None
    except Exception:
        return None
    return str(row["id"])


def create_user(username: str, password: str) -> str:
    """Create a user with a bcrypt password hash and return the new user id."""
    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")
    client = get_client()
    r = client.table("users").insert({
        "id": user_id,
        "username": username,
        "password_hash": password_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("Failed to create user")
    return str(r.data[0].get("id") or user_id)


def issue_jwt(user_id: str) -> str:
    """Return a signed JWT for the given user_id."""
    payload = {
        "sub": user_id,
        "aud": JWT_AUDIENCE,
        "exp": int(time()) + JWT_EXPIRES_SECONDS,
        "iat": int(time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    """Return payload if token is valid, else None."""
    if not token or not JWT_SECRET:
        return None
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
        )
        return payload
    except jwt.InvalidTokenError:
        return None


def get_user_id_from_request() -> str | None:
    """Extract and validate Bearer token from request; return user_id or None."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    payload = decode_jwt(token)
    if not payload:
        return None
    return payload.get("sub")


def require_auth(f):
    """Decorator: require valid JWT; set g.user_id and call view, else 401."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        user_id = get_user_id_from_request()
        if not user_id:
            return jsonify({"error": "Unauthorized", "message": "Missing or invalid token"}), 401
        g.user_id = user_id
        return f(*args, **kwargs)

    return wrapped

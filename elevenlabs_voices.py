"""Supported voices for Replicate elevenlabs/v3."""

from typing import Any

from config import SUPABASE_SAMPLE_VOICES_BASE_URL

# Allowed values taken from Replicate input validation for elevenlabs/v3.
_VOICE_NAMES = [
    "Rachel",
    "Drew",
    "Clyde",
    "Paul",
    "Aria",
    "Domi",
    "Dave",
    "Roger",
    "Fin",
    "Sarah",
    "James",
    "Jane",
    "Juniper",
    "Arabella",
    "Hope",
    "Bradford",
    "Reginald",
    "Gaming",
    "Austin",
    "Kuon",
    "Blondie",
    "Priyanka",
    "Alexandra",
    "Monika",
    "Mark",
    "Gimblewood",
]

# Keep the legacy `voice_id` key for API compatibility; model accepts the name string.
_VOICE_OPTIONS: list[dict[str, str]] = [
    {
        "name": name,
        "voice_id": name,
        "sample_url": f"{SUPABASE_SAMPLE_VOICES_BASE_URL}/{name}.mp3",
    }
    for name in _VOICE_NAMES
]

# Backward-compat for previous ElevenLabs ID values already handed to clients.
_LEGACY_ID_TO_NAME = {
    "29vD33N1CtxCmqQRPOHJ": "Drew",
    "2EiwWnXFnvU5JabPnv8n": "Clyde",
    "5Q0t7uMcjvnagumLfvZi": "Paul",
    "AZnzlk1XvdvUeBnXmlld": "Domi",
    "CYw3kZ02Hs0563khs1Fj": "Dave",
    "D38z5RcWu1voky8WS1ja": "Fin",
    "EXAVITQu4vr4xnSDxMaL": "Sarah",
    "ZQe5CZNOzWyzPSCn5a3c": "James",
    "21m00Tcm4TlvDq8ikWAM": "Rachel",
}

_BY_ID: dict[str, dict[str, str]] = {v["voice_id"]: v for v in _VOICE_OPTIONS}
_BY_NAME: dict[str, dict[str, str]] = {v["name"].strip().lower(): v for v in _VOICE_OPTIONS}


def list_supported_voices() -> list[dict[str, str]]:
    return list(_VOICE_OPTIONS)


def resolve_supported_voice(voice_input: str | None, default_voice: str = "Rachel") -> dict[str, str]:
    """
    Resolve user voice input (name or voice_id) to a supported voice entry.
    Returns {'name', 'voice_id', 'sample_url'}.
    """
    raw = (voice_input or "").strip()
    if raw:
        legacy_name = _LEGACY_ID_TO_NAME.get(raw)
        if legacy_name:
            return _BY_NAME[legacy_name.lower()]
        by_id = _BY_ID.get(raw)
        if by_id:
            return by_id
        by_name = _BY_NAME.get(raw.lower())
        if by_name:
            return by_name

    fallback = (default_voice or "Rachel").strip()
    if fallback:
        legacy_name = _LEGACY_ID_TO_NAME.get(fallback)
        if legacy_name:
            return _BY_NAME[legacy_name.lower()]
        by_id = _BY_ID.get(fallback)
        if by_id:
            return by_id
        by_name = _BY_NAME.get(fallback.lower())
        if by_name:
            return by_name

    # Last safety fallback
    return _BY_NAME["rachel"]


def validate_voice_or_raise(voice_input: str | None) -> dict[str, Any]:
    """
    Validate explicit voice selection only.
    Raises ValueError for unsupported user input.
    """
    raw = (voice_input or "").strip()
    if not raw:
        raise ValueError("Voice is empty")
    legacy_name = _LEGACY_ID_TO_NAME.get(raw)
    if legacy_name:
        return _BY_NAME[legacy_name.lower()]
    if raw in _BY_ID:
        return _BY_ID[raw]
    by_name = _BY_NAME.get(raw.lower())
    if by_name:
        return by_name
    supported = ", ".join(v["name"] for v in _VOICE_OPTIONS)
    raise ValueError(f"Unsupported voice '{raw}'. Supported voices: {supported}")

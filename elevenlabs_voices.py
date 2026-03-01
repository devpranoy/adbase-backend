"""Supported ElevenLabs voices for Replicate elevenlabs/v3."""

from typing import Any

# Source: ElevenLabs Premade Voices documentation.
# We use the premade catalog as the supported selector set for v3 usage in this backend.
_VOICE_OPTIONS: list[dict[str, str]] = [
    {"name": "Adam", "voice_id": "pNInz6obpgDQGcFmaJgB"},
    {"name": "Alice", "voice_id": "Xb7hH8MSUJpSbSDYk0k2"},
    {"name": "Antoni", "voice_id": "ErXwobaYiN019PkySvjV"},
    {"name": "Arnold", "voice_id": "VR6AewLTigWG4xSOukaG"},
    {"name": "Bill", "voice_id": "pqHfZKP75CvOlQylNhV4"},
    {"name": "Brian", "voice_id": "nPczCjzI2devNBz1zQrb"},
    {"name": "Callum", "voice_id": "N2lVS1w4EtoT3dr4eOWO"},
    {"name": "Charlie", "voice_id": "IKne3meq5aSn9XLyUdCD"},
    {"name": "Charlotte", "voice_id": "XB0fDUnXU5powFXDhCwa"},
    {"name": "Chris", "voice_id": "iP95p4xoKVk53GoZ742B"},
    {"name": "Clyde", "voice_id": "2EiwWnXFnvU5JabPnv8n"},
    {"name": "Daniel", "voice_id": "onwK4e9ZLuTAKqWW03F9"},
    {"name": "Dave", "voice_id": "CYw3kZ02Hs0563khs1Fj"},
    {"name": "Domi", "voice_id": "AZnzlk1XvdvUeBnXmlld"},
    {"name": "Dorothy", "voice_id": "ThT5KcBeYPX3keUQqHPh"},
    {"name": "Drew", "voice_id": "29vD33N1CtxCmqQRPOHJ"},
    {"name": "Emily", "voice_id": "LcfcDJNUP1GQjkzn1xUU"},
    {"name": "Ethan", "voice_id": "g5CIjZEefAph4nQFvHAz"},
    {"name": "Fin", "voice_id": "D38z5RcWu1voky8WS1ja"},
    {"name": "Freya", "voice_id": "jsCqWAovK2LkecY7zXl4"},
    {"name": "George", "voice_id": "JBFqnCBsd6RMkjVDRZzb"},
    {"name": "Gigi", "voice_id": "jBpfuIE2acCO8z3wKNLl"},
    {"name": "Giovanni", "voice_id": "zcAOhNBS3c14rBihAFp1"},
    {"name": "Glinda", "voice_id": "z9fAnlkpzviPz146aGWa"},
    {"name": "Grace", "voice_id": "oWAxZDx7w5VEj9dCyTzz"},
    {"name": "Harry", "voice_id": "SOYHLrjzK2X1ezoPC6cr"},
    {"name": "James", "voice_id": "ZQe5CZNOzWyzPSCn5a3c"},
    {"name": "Jeremy", "voice_id": "bVMeCyTHy58xNoL34h3p"},
    {"name": "Jessie", "voice_id": "t0jbNlBVZ17f02VDIeMI"},
    {"name": "Joseph", "voice_id": "Zlb1dXrM653N07WRdFW3"},
    {"name": "Josh", "voice_id": "TxGEqnHWrfWFTfGW9XjX"},
    {"name": "Liam", "voice_id": "TX3LPaxmHKxFdv7VOQHJ"},
    {"name": "Lily", "voice_id": "pFZP5JQG7iQjIQuC4Bku"},
    {"name": "Matilda", "voice_id": "XrExE9yKIg1WjnnlVkGX"},
    {"name": "Michael", "voice_id": "flq6f7yk4E4fJM5XTYuZ"},
    {"name": "Mimi", "voice_id": "zrHiDhphv9ZnVXBqCLjz"},
    {"name": "Nicole", "voice_id": "piTKgcLEGmPE4e6mEKli"},
    {"name": "Patrick", "voice_id": "ODq5zmih8GrVes37Dizd"},
    {"name": "Paul", "voice_id": "5Q0t7uMcjvnagumLfvZi"},
    {"name": "Rachel", "voice_id": "21m00Tcm4TlvDq8ikWAM"},
    {"name": "Sam", "voice_id": "yoZ06aMxZJJ28mfd3POQ"},
    {"name": "Sarah", "voice_id": "EXAVITQu4vr4xnSDxMaL"},
    {"name": "Serena", "voice_id": "pMsXgVXv3BLzUgSXRplE"},
    {"name": "Thomas", "voice_id": "GBv7mTt0atIp3Br8iCZE"},
    {"name": "Santa Claus", "voice_id": "knrPHWnBmmDHMoiMeP3l"},
]

_BY_ID: dict[str, dict[str, str]] = {v["voice_id"]: v for v in _VOICE_OPTIONS}
_BY_NAME: dict[str, dict[str, str]] = {v["name"].strip().lower(): v for v in _VOICE_OPTIONS}


def list_supported_voices() -> list[dict[str, str]]:
    return list(_VOICE_OPTIONS)


def resolve_supported_voice(voice_input: str | None, default_voice: str = "Rachel") -> dict[str, str]:
    """
    Resolve user voice input (name or voice_id) to a supported voice entry.
    Returns {'name', 'voice_id'}.
    """
    raw = (voice_input or "").strip()
    if raw:
        by_id = _BY_ID.get(raw)
        if by_id:
            return by_id
        by_name = _BY_NAME.get(raw.lower())
        if by_name:
            return by_name

    fallback = (default_voice or "Rachel").strip()
    if fallback:
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
    if raw in _BY_ID:
        return _BY_ID[raw]
    by_name = _BY_NAME.get(raw.lower())
    if by_name:
        return by_name
    supported = ", ".join(v["name"] for v in _VOICE_OPTIONS)
    raise ValueError(f"Unsupported voice '{raw}'. Supported voices: {supported}")

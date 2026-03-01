"""Replicate API: start image-to-video prediction and poll for result."""
import os

import replicate

from config import (
    REPLICATE_API_TOKEN,
    REPLICATE_IMAGE_TO_VIDEO_VERSION,
    REPLICATE_VIDEO_RESOLUTION,
    REPLICATE_VIDEO_DURATION,
    REPLICATE_VIDEO_ASPECT_RATIO,
    REPLICATE_TTS_MODEL,
    REPLICATE_TTS_VOICE,
    REPLICATE_TTS_LANGUAGE_CODE,
    REPLICATE_FABRIC_MODEL,
    REPLICATE_FABRIC_RESOLUTION,
    REPLICATE_FFMPEG_MODEL,
)
from elevenlabs_voices import resolve_supported_voice, list_supported_voices


def _ensure_token():
    if not REPLICATE_API_TOKEN:
        raise RuntimeError("REPLICATE_API_TOKEN must be set")
    os.environ.setdefault("REPLICATE_API_TOKEN", REPLICATE_API_TOKEN)


def start_image_to_video(image_url: str, prompt: str = "") -> str:
    """
    Start an image-to-video prediction. Returns the prediction id.
    Default model: Google Veo 3.1 (prompt required; image optional for img-to-video).
    """
    _ensure_token()
    # Veo 3.1 / 3.1 Fast: prompt required; image for image-to-video; optional resolution, duration, aspect_ratio
    input_params = {
        "prompt": prompt or "Smooth motion, cinematic quality",
        "image": image_url,
        "resolution": REPLICATE_VIDEO_RESOLUTION,
        "duration": REPLICATE_VIDEO_DURATION,
        "aspect_ratio": REPLICATE_VIDEO_ASPECT_RATIO,
    }
    prediction = replicate.predictions.create(
        version=REPLICATE_IMAGE_TO_VIDEO_VERSION,
        input=input_params,
    )
    return prediction.id


def get_prediction(prediction_id: str) -> tuple[str, str | None]:
    """
    Poll prediction status. Returns (status, output_video_url).
    status is one of 'starting'|'processing'|'succeeded'|'failed'|'canceled'.
    output_video_url is set when status is 'succeeded' (first file URL if multiple).
    """
    _ensure_token()
    pred = replicate.predictions.get(prediction_id)
    status = (pred.status or "unknown").lower()
    output_url = None
    if status == "succeeded" and pred.output:
        out = pred.output
        if isinstance(out, list) and len(out) > 0:
            output_url = out[0] if isinstance(out[0], str) else getattr(out[0], "url", None)
        elif isinstance(out, str):
            output_url = out
    return status, output_url


def _extract_output_url(output: object) -> str | None:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and len(output) > 0:
        first = output[0]
        if isinstance(first, str):
            return first
        return getattr(first, "url", None)
    if hasattr(output, "url"):
        return getattr(output, "url", None)
    if isinstance(output, dict):
        for key in ("output", "audio", "audio_url", "url"):
            val = output.get(key)
            if isinstance(val, str):
                return val
    return None


def _run_model_with_fallback_inputs(model: str, candidate_inputs: list[dict]) -> object:
    last_error = None
    for input_payload in candidate_inputs:
        try:
            return replicate.run(model, input=input_payload)
        except Exception as e:
            last_error = e
            continue
    if last_error:
        raise RuntimeError(f"Replicate model call failed for {model}: {last_error}")
    raise RuntimeError(f"Replicate model call failed for {model}")


def run_image_to_video(image_url: str, prompt: str = "") -> str:
    """
    Run image-to-video synchronously and return output video URL.
    """
    _ensure_token()
    input_payload = {
        "prompt": prompt or "Smooth motion, cinematic quality",
        "image": image_url,
        "resolution": REPLICATE_VIDEO_RESOLUTION,
        "duration": REPLICATE_VIDEO_DURATION,
        "aspect_ratio": REPLICATE_VIDEO_ASPECT_RATIO,
    }
    output = replicate.run(REPLICATE_IMAGE_TO_VIDEO_VERSION, input=input_payload)
    output_url = _extract_output_url(output)
    if not output_url:
        raise RuntimeError("Replicate image-to-video output missing video URL")
    return output_url


def generate_tts_audio(
    prompt: str,
    voice: str | None = None,
    *,
    language_code: str | None = None,
    speed: float | None = None,
    stability: float | None = None,
    similarity_boost: float | None = None,
    style: float | None = None,
) -> str:
    """
    Generate TTS audio using Replicate elevenlabs/v3 and return audio URL.
    """
    _ensure_token()
    text = (prompt or "").strip()
    if not text:
        raise ValueError("prompt is required")
    voice_entry = resolve_supported_voice(voice_input=voice, default_voice=REPLICATE_TTS_VOICE)

    input_payload = {
        "prompt": text,
        "voice": voice_entry["name"],
        "language_code": (language_code or REPLICATE_TTS_LANGUAGE_CODE or "en").strip(),
    }
    if speed is not None:
        input_payload["speed"] = speed
    if stability is not None:
        input_payload["stability"] = stability
    if similarity_boost is not None:
        input_payload["similarity_boost"] = similarity_boost
    if style is not None:
        input_payload["style"] = style

    output = replicate.run(REPLICATE_TTS_MODEL, input=input_payload)
    output_url = _extract_output_url(output)
    if not output_url:
        raise RuntimeError("Replicate TTS output missing audio URL")
    return output_url


def get_supported_tts_voices() -> list[dict[str, str]]:
    """Return supported ElevenLabs voice options for UI selection."""
    return list_supported_voices()


def generate_ugc_hook_video(actor_image_url: str, audio_url: str, prompt: str = "") -> str:
    """
    Generate a talking-head UGC hook video using Fabric model and return output video URL.
    """
    _ensure_token()
    image = (actor_image_url or "").strip()
    audio = (audio_url or "").strip()
    if not image:
        raise ValueError("actor_image_url is required")
    if not audio:
        raise ValueError("audio_url is required")

    candidate_inputs = [
        {
            "prompt": prompt or "Natural UGC talking head delivery",
            "image": image,
            "audio": audio,
            "resolution": REPLICATE_FABRIC_RESOLUTION,
        },
        {
            "prompt": prompt or "Natural UGC talking head delivery",
            "input_image": image,
            "input_audio": audio,
            "resolution": REPLICATE_FABRIC_RESOLUTION,
        },
        {
            "prompt": prompt or "Natural UGC talking head delivery",
            "image": image,
            "audio_file": audio,
            "resolution": REPLICATE_FABRIC_RESOLUTION,
        },
    ]
    output = _run_model_with_fallback_inputs(REPLICATE_FABRIC_MODEL, candidate_inputs)
    output_url = _extract_output_url(output)
    if not output_url:
        raise RuntimeError("Fabric output missing video URL")
    return output_url


def stitch_videos(video_urls: list[str]) -> str:
    """
    Stitch videos into one output using merge model on Replicate. Returns output video URL.
    """
    _ensure_token()
    clean_urls = [u.strip() for u in (video_urls or []) if isinstance(u, str) and u.strip()]
    if len(clean_urls) < 2:
        raise ValueError("At least 2 video URLs are required for stitching")

    # Expected order for downstream ad flow: UGC hook first, product video second.
    first_video = clean_urls[0]
    second_video = clean_urls[1]

    candidate_inputs = [
        {"video_files": [first_video, second_video], "keep_audio": True},
        {"videos": [first_video, second_video], "keep_audio": True},
        {"video_urls": [first_video, second_video], "keep_audio": True},
        {"video1": first_video, "video2": second_video, "keep_audio": True},
        {"input_video_1": first_video, "input_video_2": second_video, "keep_audio": True},
    ]
    output = _run_model_with_fallback_inputs(REPLICATE_FFMPEG_MODEL, candidate_inputs)
    output_url = _extract_output_url(output)
    if not output_url:
        raise RuntimeError("FFmpeg stitch output missing video URL")
    return output_url

"""Replicate API: start image-to-video prediction and poll for result."""
import os

import replicate

from config import (
    REPLICATE_API_TOKEN,
    REPLICATE_IMAGE_TO_VIDEO_VERSION,
    REPLICATE_VIDEO_RESOLUTION,
    REPLICATE_VIDEO_DURATION,
    REPLICATE_VIDEO_ASPECT_RATIO,
)


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

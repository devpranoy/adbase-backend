"""Generate ad hook scripts and story prompts from a user prompt."""
import json
import re
from typing import Any

import os

import replicate

from config import REPLICATE_API_TOKEN, REPLICATE_TEXT_MODEL


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _extract_product_hint(prompt: str) -> str:
    cleaned = _normalize_text(prompt)
    if not cleaned:
        return "the product"
    # Prefer short leading segment as a practical product hint.
    parts = re.split(r"[.!?;:]", cleaned)
    head = (parts[0] or "").strip()
    if 2 <= len(head.split()) <= 12:
        return head
    words = cleaned.split()
    return " ".join(words[:8]) if words else "the product"


def _local_script_writer(user_prompt: str, tone: str, duration_target_sec: int) -> dict[str, Any]:
    product_hint = _extract_product_hint(user_prompt)
    hook_text = (
        f"I tried {product_hint}, and honestly this changed my routine in under a week. "
        "If you want something simple that actually works, watch this."
    )
    lines = [
        f"I tried {product_hint}, and honestly this changed my routine in under a week.",
        "If you want something simple that actually works, watch this.",
    ]
    return {
        "hook_text": hook_text,
        "hook_lines": lines,
        "tone": tone or "conversational",
        "duration_target_sec": duration_target_sec,
    }


def _local_story_writer(
    user_prompt: str,
    image_url: str,
    hook_text: str,
    duration_target_sec: int,
) -> dict[str, Any]:
    product_hint = _extract_product_hint(user_prompt)
    image_reference = (
        f"Use this product image as visual reference: {image_url}. "
        if image_url
        else "Use a product-focused visual style with clean packaging close-ups. "
    )
    video_prompt = (
        "Generate a vertical UGC-style ad video (9:16, cinematic but natural lighting). "
        f"{image_reference}"
        f"Open with a talking-head style setup matching the hook: '{hook_text}'. "
        "Then show quick product closeups, usage moments, and one clear benefit outcome. "
        "Camera motion should feel handheld and authentic, not studio-perfect. "
        "Keep pacing punchy, social-first, with on-screen text room in safe margins. "
        f"Total story segment duration target: {max(duration_target_sec, 4)} to 8 seconds. "
        f"End with a clear CTA card: 'Try {product_hint} today'."
    )
    return {
        "video_prompt": video_prompt,
        "cta": f"Try {product_hint} today",
        "shot_plan": [
            "Shot 1: hook-aligned opening frame, creator-style delivery",
            "Shot 2: product close-up with texture/details",
            "Shot 3: in-use action moment",
            "Shot 4: result reveal + CTA",
        ],
    }


def _coerce_int(value: Any, default: int, min_v: int, max_v: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_v, min(max_v, parsed))


def _ensure_replicate_token() -> bool:
    if not REPLICATE_API_TOKEN:
        return False
    os.environ.setdefault("REPLICATE_API_TOKEN", REPLICATE_API_TOKEN)
    return True


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    # Handle cases where model wraps JSON with prose or code fences.
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _call_replicate_json(prompt: str) -> dict[str, Any] | None:
    if not _ensure_replicate_token():
        return None
    candidate_inputs = [
        {"prompt": prompt, "temperature": 0.5, "max_tokens": 700},
        {"prompt": prompt},
    ]
    output = None
    for input_payload in candidate_inputs:
        try:
            output = replicate.run(REPLICATE_TEXT_MODEL, input=input_payload)
            break
        except Exception:
            output = None
            continue
    if output is None:
        return None

    if isinstance(output, str):
        text = output
    elif isinstance(output, list):
        text = "".join(str(part) for part in output)
    elif hasattr(output, "__iter__"):
        try:
            text = "".join(str(part) for part in output)
        except Exception:
            text = str(output or "")
    else:
        text = str(output or "")
    return _extract_json_object(text)


def _replicate_agent_generation(
    user_prompt: str,
    image_url: str,
    tone: str,
    duration_target_sec: int,
) -> dict[str, Any] | None:
    if not REPLICATE_TEXT_MODEL:
        return None
    system_prompt = (
        "You are an ad creative system. Return strict JSON only with keys: "
        "script_writer {hook_text, hook_lines[], tone, duration_target_sec} and "
        "story_writer {video_prompt, cta, shot_plan[]}. "
        "The story_writer video_prompt MUST strictly describe a vertical portrait 9:16 video. "
        "Compose every subject, product, camera movement, and safe margin specifically for a 9:16 mobile frame; "
        "never request landscape, widescreen, 16:9, square, or horizontal output."
    )
    user_content = {
        "user_prompt": user_prompt,
        "image_url": image_url,
        "tone": tone,
        "duration_target_sec": duration_target_sec,
        "requirements": [
            "script_writer hook must feel UGC, natural, direct",
            "story_writer video_prompt must be ready for image-to-video generation",
            "story_writer video_prompt must explicitly require strict vertical portrait 9:16 composition",
            "output must be concise and production-usable",
        ],
    }
    prompt = (
        f"{system_prompt}\n\n"
        "Return only valid JSON. Do not include markdown.\n\n"
        f"Input:\n{json.dumps(user_content)}"
    )
    out = _call_replicate_json(prompt)
    if not out:
        return None
    if not isinstance(out, dict):
        return None
    if not isinstance(out.get("script_writer"), dict):
        return None
    if not isinstance(out.get("story_writer"), dict):
        return None
    return out


def generate_ad_agents(
    user_prompt: str,
    image_url: str = "",
    tone: str = "conversational",
    duration_target_sec: int = 5,
) -> dict[str, Any]:
    """
    Generate outputs from script_writer and story_writer agents.
    Uses Replicate text model when configured, else deterministic local fallback.
    """
    cleaned_prompt = _normalize_text(user_prompt)
    if not cleaned_prompt:
        raise ValueError("Prompt is required")

    safe_duration = _coerce_int(duration_target_sec, default=5, min_v=3, max_v=12)
    tone = _normalize_text(tone) or "conversational"
    llm_result = _replicate_agent_generation(cleaned_prompt, image_url or "", tone, safe_duration)
    if llm_result:
        script_writer = llm_result.get("script_writer") or {}
        story_writer = llm_result.get("story_writer") or {}
        hook_text = _normalize_text(str(script_writer.get("hook_text") or ""))
        if not hook_text:
            script_writer = _local_script_writer(cleaned_prompt, tone, safe_duration)
            hook_text = script_writer["hook_text"]
        if not story_writer.get("video_prompt"):
            story_writer = _local_story_writer(cleaned_prompt, image_url or "", hook_text, safe_duration)
        return {
            "script_writer": script_writer,
            "story_writer": story_writer,
            "meta": {"provider": "replicate", "model": REPLICATE_TEXT_MODEL},
        }

    script_writer = _local_script_writer(cleaned_prompt, tone, safe_duration)
    story_writer = _local_story_writer(cleaned_prompt, image_url or "", script_writer["hook_text"], safe_duration)
    return {
        "script_writer": script_writer,
        "story_writer": story_writer,
        "meta": {"provider": "local-fallback", "model": "template-v1"},
    }

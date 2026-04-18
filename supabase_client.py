"""Supabase client and storage helpers."""
import json
import os
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

from supabase import create_client

from config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_BUCKET_PRODUCT_IMAGES,
    SUPABASE_BUCKET_VIDEOS,
    SUPABASE_BUCKET_AUDIO,
    SUPABASE_BUCKET_ACTORS,
)

_client = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_client():
    """Return a single Supabase client instance (service role)."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _client


def upload_product_image(file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """
    Upload a product image to Supabase Storage and return its public URL.
    Uses bucket name from config (default: product-images). Bucket must be public.
    """
    client = get_client()
    storage = client.storage.from_(SUPABASE_BUCKET_PRODUCT_IMAGES)
    # Use a path that includes filename to avoid collisions; optionally add UUID in real use
    path = f"uploads/{filename}"
    storage.upload(path, file_bytes, file_options={"content-type": content_type})
    return storage.get_public_url(path)


def upload_actor_image(file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """
    Upload a user-provided actor image to Supabase Storage and return its public URL.
    Uses the dedicated actor-images bucket so reusable actors stay separate from product assets.
    """
    client = get_client()
    storage = client.storage.from_(SUPABASE_BUCKET_ACTORS)
    path = f"uploads/{filename}"
    storage.upload(path, file_bytes, file_options={"content-type": content_type, "upsert": "true"})
    return storage.get_public_url(path)


def _with_variant(job_id: str, variant: str | None, ext: str) -> str:
    safe_variant = (variant or "").strip()
    if safe_variant:
        return f"completed/{job_id}-{safe_variant}.{ext}"
    return f"completed/{job_id}.{ext}"


def upload_video(
    video_bytes: bytes,
    job_id: str,
    *,
    variant: str | None = None,
    ext: str = "mp4",
    content_type: str = "video/mp4",
) -> str:
    """
    Upload a video to Supabase Storage (product-videos bucket) and return its public URL.
    Path: completed/<job_id>-<variant>.<ext> (or completed/<job_id>.<ext> when variant omitted).
    Bucket must be public.
    """
    client = get_client()
    storage = client.storage.from_(SUPABASE_BUCKET_VIDEOS)
    path = _with_variant(job_id, variant, ext)
    storage.upload(path, video_bytes, file_options={"content-type": content_type, "upsert": "true"})
    return storage.get_public_url(path)


def _guess_audio_extension(content_type: str, source_url: str) -> str:
    if content_type == "audio/wav":
        return "wav"
    if content_type == "audio/ogg":
        return "ogg"
    if content_type == "audio/flac":
        return "flac"
    if content_type in {"audio/mpeg", "audio/mp3"}:
        return "mp3"
    path = urlparse(source_url).path or ""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext in {"mp3", "wav", "ogg", "flac", "m4a"}:
        return ext
    return "mp3"


def _guess_image_extension(content_type: str, source_url: str) -> str:
    if content_type == "image/png":
        return "png"
    if content_type == "image/webp":
        return "webp"
    if content_type == "image/gif":
        return "gif"
    path = urlparse(source_url).path or ""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "jpg" if ext == "jpeg" else ext
    return "jpg"


def upload_audio(
    audio_bytes: bytes,
    job_id: str,
    ext: str = "mp3",
    content_type: str = "audio/mpeg",
    *,
    variant: str | None = None,
) -> str:
    """
    Upload an audio file to Supabase Storage (product-audio bucket) and return its public URL.
    Path: completed/<job_id>-<variant>.<ext> (or completed/<job_id>.<ext> when variant omitted).
    Bucket must be public.
    """
    client = get_client()
    storage = client.storage.from_(SUPABASE_BUCKET_AUDIO)
    path = _with_variant(job_id, variant, ext)
    storage.upload(path, audio_bytes, file_options={"content-type": content_type, "upsert": "true"})
    return storage.get_public_url(path)


def persist_replicate_video(replicate_video_url: str, job_id: str, *, variant: str | None = None) -> str:
    """
    Download video from Replicate URL and upload to our storage. Returns our permanent URL.
    Use this when a job succeeds so the link does not expire after 1 hour.
    """
    req = urllib.request.Request(
        replicate_video_url,
        headers={"User-Agent": "AdbaseBackend/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        video_bytes = resp.read()
        content_type = (resp.headers.get_content_type() or "video/mp4").lower()
    ext = "mp4"
    path_ext = os.path.splitext(urlparse(replicate_video_url).path or "")[1].lower().lstrip(".")
    if path_ext in {"mp4", "mov", "webm"}:
        ext = path_ext
    return upload_video(video_bytes, job_id, variant=variant, ext=ext, content_type=content_type)


def persist_replicate_audio(replicate_audio_url: str, job_id: str, *, variant: str | None = None) -> str:
    """
    Download audio from Replicate URL and upload to our storage. Returns our permanent URL.
    """
    req = urllib.request.Request(
        replicate_audio_url,
        headers={"User-Agent": "AdbaseBackend/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        audio_bytes = resp.read()
        content_type = (resp.headers.get_content_type() or "audio/mpeg").lower()
    ext = _guess_audio_extension(content_type, replicate_audio_url)
    return upload_audio(audio_bytes, job_id, ext=ext, content_type=content_type, variant=variant)


def persist_replicate_actor_image(replicate_image_url: str, actor_id: str, actor_variant_id: str) -> str:
    """
    Download an image from Replicate and store it in the actor-images bucket.
    """
    req = urllib.request.Request(
        replicate_image_url,
        headers={"User-Agent": "AdbaseBackend/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        image_bytes = resp.read()
        content_type = (resp.headers.get_content_type() or "image/jpeg").lower()

    ext = _guess_image_extension(content_type, replicate_image_url)
    client = get_client()
    storage = client.storage.from_(SUPABASE_BUCKET_ACTORS)
    path = f"generated/{actor_id}/{actor_variant_id}.{ext}"
    storage.upload(path, image_bytes, file_options={"content-type": content_type, "upsert": "true"})
    return storage.get_public_url(path)


def save_pipeline_manifest(job_id: str, manifest: dict) -> str:
    """
    Save pipeline artifact metadata to videos bucket under manifests/<job_id>.json.
    Returns public URL.
    """
    client = get_client()
    storage = client.storage.from_(SUPABASE_BUCKET_VIDEOS)
    path = f"manifests/{job_id}.json"
    payload = json.dumps(manifest, ensure_ascii=True).encode("utf-8")
    storage.upload(path, payload, file_options={"content-type": "application/json", "upsert": "true"})
    return storage.get_public_url(path)


def get_pipeline_manifest(job_id: str) -> dict | None:
    """
    Read pipeline artifact metadata from videos bucket manifest.
    """
    client = get_client()
    storage = client.storage.from_(SUPABASE_BUCKET_VIDEOS)
    path = f"manifests/{job_id}.json"
    try:
        signed = storage.create_signed_url(path, 60)
        signed_url = (signed or {}).get("signedURL")
        if not signed_url:
            return None
        if signed_url.startswith("/"):
            signed_url = f"{SUPABASE_URL.rstrip('/')}{signed_url}"
        with urllib.request.urlopen(signed_url, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# --- Jobs table helpers ---


def create_job(user_id: str, image_url: str, prompt: str, actor_variant_id: str | None = None) -> dict:
    """Insert a draft job and return the row (with id)."""
    client = get_client()
    row = {
        "user_id": user_id,
        "image_url": image_url,
        "prompt": prompt or "",
        "status": "draft",
        "actor_variant_id": actor_variant_id,
    }
    r = client.table("jobs").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("Failed to create job")
    return r.data[0]


def get_job(job_id: str, user_id: str) -> dict | None:
    """Return job row if it exists and belongs to user_id, else None."""
    client = get_client()
    r = client.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).limit(1).execute()
    if not r.data or len(r.data) == 0:
        return None
    return r.data[0]


def list_jobs(user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    """Return jobs for user_id, newest first. Optional limit (default 50) and offset for pagination."""
    client = get_client()
    r = (
        client.table("jobs")
        .select("id, status, image_url, prompt, output_video_url, actor_variant_id, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return r.data or []


def update_job_prediction(job_id: str, user_id: str, replicate_prediction_id: str) -> None:
    """Set replicate_prediction_id and status=processing."""
    client = get_client()
    client.table("jobs").update({
        "replicate_prediction_id": replicate_prediction_id,
        "status": "processing",
        "updated_at": _now_iso(),
    }).eq("id", job_id).eq("user_id", user_id).execute()


def update_job_result(job_id: str, user_id: str, output_video_url: str | None, status: str) -> None:
    """Set output_video_url and status (succeeded or failed)."""
    client = get_client()
    payload = {"status": status, "updated_at": _now_iso()}
    if output_video_url is not None:
        payload["output_video_url"] = output_video_url
    client.table("jobs").update(payload).eq("id", job_id).eq("user_id", user_id).execute()


def update_job_status(job_id: str, user_id: str, status: str) -> None:
    """Set status field for a job."""
    client = get_client()
    client.table("jobs").update({"status": status, "updated_at": _now_iso()}).eq("id", job_id).eq("user_id", user_id).execute()


def update_job_actor_variant(job_id: str, user_id: str, actor_variant_id: str | None) -> None:
    """Associate a job with a selected actor variant."""
    client = get_client()
    client.table("jobs").update({
        "actor_variant_id": actor_variant_id,
        "updated_at": _now_iso(),
    }).eq("id", job_id).eq("user_id", user_id).execute()


# --- Actors / actor_variants helpers ---


def create_actor(
    user_id: str,
    *,
    name: str | None,
    age_band: str,
    ethnicity: str,
    gender_presentation: str | None,
    prompt: str,
    attributes: dict | list | str | None,
    status: str = "draft",
) -> dict:
    client = get_client()
    row = {
        "user_id": user_id,
        "name": name or None,
        "status": status,
        "age_band": age_band,
        "ethnicity": ethnicity,
        "gender_presentation": gender_presentation or None,
        "prompt": prompt,
        "attributes": attributes if attributes is not None else {},
    }
    r = client.table("actors").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("Failed to create actor")
    return r.data[0]


def get_actor(actor_id: str, user_id: str) -> dict | None:
    client = get_client()
    r = client.table("actors").select("*").eq("id", actor_id).eq("user_id", user_id).limit(1).execute()
    if not r.data or len(r.data) == 0:
        return None
    return r.data[0]


def list_actors(user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    client = get_client()
    r = (
        client.table("actors")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return r.data or []


def update_actor(actor_id: str, user_id: str, payload: dict) -> None:
    client = get_client()
    clean_payload = dict(payload)
    clean_payload["updated_at"] = _now_iso()
    client.table("actors").update(clean_payload).eq("id", actor_id).eq("user_id", user_id).execute()


def update_actor_status(actor_id: str, user_id: str, status: str) -> None:
    update_actor(actor_id, user_id, {"status": status})


def create_actor_variant(
    actor_id: str,
    user_id: str,
    *,
    status: str = "generating",
    image_url: str | None = None,
    thumbnail_url: str | None = None,
    prompt: str | None = None,
    replicate_model: str | None = None,
    replicate_prediction_id: str | None = None,
    seed: str | None = None,
    metadata: dict | list | str | None = None,
    is_primary: bool = False,
) -> dict:
    client = get_client()
    row = {
        "actor_id": actor_id,
        "user_id": user_id,
        "status": status,
        "image_url": image_url,
        "thumbnail_url": thumbnail_url,
        "prompt": prompt or "",
        "replicate_model": replicate_model,
        "replicate_prediction_id": replicate_prediction_id,
        "seed": seed,
        "metadata": metadata if metadata is not None else {},
        "is_primary": is_primary,
    }
    r = client.table("actor_variants").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("Failed to create actor variant")
    return r.data[0]


def get_actor_variant(actor_variant_id: str, user_id: str) -> dict | None:
    client = get_client()
    r = (
        client.table("actor_variants")
        .select("*")
        .eq("id", actor_variant_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    return r.data[0]


def list_actor_variants(actor_id: str, user_id: str) -> list[dict]:
    client = get_client()
    r = (
        client.table("actor_variants")
        .select("*")
        .eq("actor_id", actor_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return r.data or []


def get_primary_actor_variant(actor_id: str, user_id: str) -> dict | None:
    client = get_client()
    r = (
        client.table("actor_variants")
        .select("*")
        .eq("actor_id", actor_id)
        .eq("user_id", user_id)
        .eq("is_primary", True)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    return r.data[0]


def update_actor_variant(actor_variant_id: str, user_id: str, payload: dict) -> None:
    client = get_client()
    clean_payload = dict(payload)
    clean_payload["updated_at"] = _now_iso()
    client.table("actor_variants").update(clean_payload).eq("id", actor_variant_id).eq("user_id", user_id).execute()


def set_primary_actor_variant(actor_id: str, user_id: str, actor_variant_id: str) -> None:
    client = get_client()
    client.table("actor_variants").update({
        "is_primary": False,
        "updated_at": _now_iso(),
    }).eq("actor_id", actor_id).eq("user_id", user_id).execute()
    client.table("actor_variants").update({
        "is_primary": True,
        "updated_at": _now_iso(),
    }).eq("id", actor_variant_id).eq("actor_id", actor_id).eq("user_id", user_id).execute()

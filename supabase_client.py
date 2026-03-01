"""Supabase client and storage helpers."""
import json
import os
import urllib.request
from urllib.parse import urlparse

from supabase import create_client

from config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_BUCKET_PRODUCT_IMAGES,
    SUPABASE_BUCKET_VIDEOS,
    SUPABASE_BUCKET_AUDIO,
)

_client = None


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


def create_job(user_id: str, image_url: str, prompt: str) -> dict:
    """Insert a draft job and return the row (with id)."""
    client = get_client()
    row = {
        "user_id": user_id,
        "image_url": image_url,
        "prompt": prompt or "",
        "status": "draft",
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
        .select("id, status, image_url, prompt, output_video_url, created_at")
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
    }).eq("id", job_id).eq("user_id", user_id).execute()


def update_job_result(job_id: str, user_id: str, output_video_url: str | None, status: str) -> None:
    """Set output_video_url and status (succeeded or failed)."""
    client = get_client()
    payload = {"status": status}
    if output_video_url is not None:
        payload["output_video_url"] = output_video_url
    client.table("jobs").update(payload).eq("id", job_id).eq("user_id", user_id).execute()


def update_job_status(job_id: str, user_id: str, status: str) -> None:
    """Set status field for a job."""
    client = get_client()
    client.table("jobs").update({"status": status}).eq("id", job_id).eq("user_id", user_id).execute()

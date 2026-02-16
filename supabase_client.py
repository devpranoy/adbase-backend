"""Supabase client and storage helpers."""
from supabase import create_client

from config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_BUCKET_PRODUCT_IMAGES,
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

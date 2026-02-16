import uuid

from flask import Blueprint, g, jsonify, request

from auth import require_auth, verify_user, issue_jwt
from supabase_client import (
    upload_product_image,
    create_job,
    get_job,
    list_jobs,
    update_job_prediction,
    update_job_result,
)
from replicate_client import start_image_to_video, get_prediction

api_bp = Blueprint("api", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"image/jpeg", "image/png", "image/webp", "image/gif"}


# --- Auth ---


@api_bp.post("/api/auth/login")
def login():
    """POST /api/auth/login with JSON { "username", "password" }. Returns { "token": "..." }."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user_id = verify_user(username, password)
    if not user_id:
        return jsonify({"error": "Invalid username or password"}), 401
    token = issue_jwt(user_id)
    return jsonify({"token": token})


# --- Jobs (all require Bearer token) ---


@api_bp.get("/api/jobs")
@require_auth
def list_user_jobs():
    """GET /api/jobs: list current user's generations (newest first). Query: limit (default 50), offset (default 0)."""
    try:
        limit = min(int(request.args.get("limit", 50)), 100)
    except (TypeError, ValueError):
        limit = 50
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except (TypeError, ValueError):
        offset = 0
    jobs = list_jobs(str(g.user_id), limit=limit, offset=offset)
    return jsonify({"jobs": jobs, "total": len(jobs)})


@api_bp.post("/api/jobs/upload")
@require_auth
def upload_job():
    """POST /api/jobs/upload: multipart form with 'image' file and 'prompt' (optional). Returns job_id and image_url."""
    if "image" not in request.files:
        return jsonify({"error": "Missing 'image' file"}), 400
    file = request.files["image"]
    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400
    if file.content_type and file.content_type not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": "Invalid image type"}), 400
    prompt = (request.form.get("prompt") or "").strip()
    try:
        file_bytes = file.read()
        content_type = file.content_type or "image/jpeg"
        image_url = upload_product_image(file_bytes, file.filename, content_type)
        job = create_job(str(g.user_id), image_url, prompt)
    except Exception as e:
        return jsonify({"error": "Upload failed", "message": str(e)}), 500
    return jsonify({
        "job_id": job["id"],
        "image_url": job["image_url"],
        "prompt": job["prompt"],
        "status": job["status"],
    }), 201


@api_bp.post("/api/jobs/<job_id>/start")
@require_auth
def start_job(job_id: str):
    """POST /api/jobs/<job_id>/start: start Replicate prediction for a draft job."""
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job_id"}), 400
    job = get_job(job_id, str(g.user_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] != "draft":
        return jsonify({"error": "Job already started or finished", "status": job["status"]}), 400
    try:
        prediction_id = start_image_to_video(job["image_url"], job.get("prompt") or "")
        update_job_prediction(job_id, str(g.user_id), prediction_id)
    except Exception as e:
        return jsonify({"error": "Failed to start job", "message": str(e)}), 500
    return jsonify({
        "job_id": job_id,
        "prediction_id": prediction_id,
        "status": "processing",
    })


@api_bp.get("/api/jobs/<job_id>")
@require_auth
def get_job_status(job_id: str):
    """GET /api/jobs/<job_id>: return job status; if processing, poll Replicate and update DB."""
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job_id"}), 400
    job = get_job(job_id, str(g.user_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] == "processing" and job.get("replicate_prediction_id"):
        try:
            status, output_url = get_prediction(job["replicate_prediction_id"])
            if status == "succeeded" and output_url:
                update_job_result(job_id, str(g.user_id), output_url, "succeeded")
                job = get_job(job_id, str(g.user_id)) or job
            elif status == "failed" or status == "canceled":
                update_job_result(job_id, str(g.user_id), None, "failed")
                job = get_job(job_id, str(g.user_id)) or job
        except Exception:
            pass
    return jsonify({
        "job_id": job["id"],
        "status": job["status"],
        "image_url": job.get("image_url"),
        "prompt": job.get("prompt"),
        "replicate_prediction_id": job.get("replicate_prediction_id"),
        "output_video_url": job.get("output_video_url"),
        "created_at": job.get("created_at"),
    })


@api_bp.get("/api/jobs/<job_id>/result")
@require_auth
def get_job_result(job_id: str):
    """GET /api/jobs/<job_id>/result: return video URL if succeeded, 202 if still processing."""
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job_id"}), 400
    job = get_job(job_id, str(g.user_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] == "processing":
        try:
            status, output_url = get_prediction(job.get("replicate_prediction_id") or "")
            if status == "succeeded" and output_url:
                update_job_result(job_id, str(g.user_id), output_url, "succeeded")
                job = get_job(job_id, str(g.user_id)) or job
        except Exception:
            pass
    if job["status"] == "succeeded" and job.get("output_video_url"):
        return jsonify({"output_video_url": job["output_video_url"]})
    if job["status"] == "processing":
        return jsonify({"status": "processing", "message": "Video not ready yet"}), 202
    if job["status"] == "failed":
        return jsonify({"error": "Job failed"}), 500
    return jsonify({"status": job["status"], "message": "No video result yet"}), 202


# --- Legacy sample endpoints (optional) ---


@api_bp.get("/api/data")
def get_sample_data():
    return jsonify(
        {
            "data": [
                {"id": 1, "name": "Sample Item 1", "value": 100},
                {"id": 2, "name": "Sample Item 2", "value": 200},
                {"id": 3, "name": "Sample Item 3", "value": 300},
            ],
            "total": 3,
            "timestamp": "2024-01-01T00:00:00Z",
        }
    )


@api_bp.get("/api/items/<int:item_id>")
def get_item(item_id: int):
    return jsonify(
        {
            "item": {
                "id": item_id,
                "name": f"Sample Item {item_id}",
                "value": item_id * 100,
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
    )

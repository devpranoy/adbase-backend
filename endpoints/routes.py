import uuid
import json
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from ad_agents import generate_ad_agents
from auth import require_auth, verify_user, issue_jwt
from supabase_client import (
    upload_product_image,
    create_job,
    get_job,
    list_jobs,
    persist_replicate_video,
    persist_replicate_audio,
    save_pipeline_manifest,
    get_pipeline_manifest,
    update_job_prediction,
    update_job_result,
    update_job_status,
)
from replicate_client import (
    start_image_to_video,
    get_prediction,
    generate_tts_audio,
    get_supported_tts_voices,
    generate_ugc_hook_video,
    run_image_to_video,
    stitch_videos,
)
from elevenlabs_voices import validate_voice_or_raise, resolve_supported_voice

api_bp = Blueprint("api", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _as_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_json_field(raw: str):
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _build_agent_prompt(user_prompt: str, product_info) -> str:
    base = (user_prompt or "").strip()
    if product_info is None:
        return base
    if isinstance(product_info, str):
        info = product_info.strip()
        if not info:
            return base
        return f"{base}\n\nProduct info:\n{info}".strip()
    return f"{base}\n\nProduct info:\n{json.dumps(product_info, ensure_ascii=True)}".strip()


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


@api_bp.get("/api/voices/elevenlabs-v3")
@require_auth
def list_elevenlabs_voices():
    """GET /api/voices/elevenlabs-v3: supported voice options for TTS."""
    voices = get_supported_tts_voices()
    default_voice = resolve_supported_voice(None)
    return jsonify({"voices": voices, "default_voice": default_voice})


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


@api_bp.post("/api/jobs/upload-full")
@require_auth
def upload_full_job():
    """
    POST /api/jobs/upload-full: multipart upload for full pipeline.
    Accepts actor image + product images + prompt + optional voice/product_info.
    """
    prompt = (request.form.get("prompt") or "").strip()
    voice_raw = (request.form.get("voice") or "").strip()
    voice = None
    if voice_raw:
        try:
            voice = validate_voice_or_raise(voice_raw)["name"]
        except ValueError as e:
            return jsonify({"error": "Invalid voice", "message": str(e)}), 400
    product_info = _parse_json_field(request.form.get("product_info") or "")

    actor_file = request.files.get("actor_image")
    product_files = request.files.getlist("product_images")
    if not product_files and "image" in request.files:
        product_files = [request.files["image"]]
    valid_product_files = [f for f in product_files if f and f.filename]
    if not valid_product_files:
        return jsonify({"error": "Missing product image(s). Use 'product_images' or 'image'"}), 400

    try:
        product_image_urls = []
        for file in valid_product_files:
            if file.content_type and file.content_type not in ALLOWED_IMAGE_EXTENSIONS:
                return jsonify({"error": f"Invalid product image type: {file.content_type}"}), 400
            file_bytes = file.read()
            image_url = upload_product_image(file_bytes, file.filename, file.content_type or "image/jpeg")
            product_image_urls.append(image_url)

        actor_image_url = None
        if actor_file and actor_file.filename:
            if actor_file.content_type and actor_file.content_type not in ALLOWED_IMAGE_EXTENSIONS:
                return jsonify({"error": f"Invalid actor image type: {actor_file.content_type}"}), 400
            actor_bytes = actor_file.read()
            actor_image_url = upload_product_image(
                actor_bytes,
                actor_file.filename,
                actor_file.content_type or "image/jpeg",
            )

        job = create_job(str(g.user_id), product_image_urls[0], prompt)
        manifest = {
            "job_id": job["id"],
            "user_id": str(g.user_id),
            "inputs": {
                "prompt": prompt,
                "voice": voice or None,
                "product_info": product_info,
                "actor_image_url": actor_image_url,
                "product_image_urls": product_image_urls,
            },
            "artifacts": {},
            "status": "draft",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_url = save_pipeline_manifest(job["id"], manifest)
    except Exception as e:
        return jsonify({"error": "Upload failed", "message": str(e)}), 500

    return jsonify({
        "job_id": job["id"],
        "status": job["status"],
        "prompt": prompt,
        "voice": voice or None,
        "product_info": product_info,
        "actor_image_url": actor_image_url,
        "product_image_urls": product_image_urls,
        "manifest_url": manifest_url,
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
    body = request.get_json(silent=True) or {}
    prompt_override = (body.get("prompt_override") or "").strip()
    use_agents = _as_bool(body.get("use_agents"), False)
    tone = (body.get("tone") or "conversational").strip()
    duration_target_sec = body.get("duration_target_sec", 5)
    effective_prompt = prompt_override or (job.get("prompt") or "")
    agent_outputs = None
    if use_agents:
        try:
            agent_outputs = generate_ad_agents(
                user_prompt=effective_prompt,
                image_url=job.get("image_url") or "",
                tone=tone,
                duration_target_sec=duration_target_sec,
            )
            effective_prompt = (
                ((agent_outputs.get("story_writer") or {}).get("video_prompt") or "").strip()
                or effective_prompt
            )
        except Exception as e:
            return jsonify({"error": "Failed to generate agent outputs", "message": str(e)}), 500
    try:
        prediction_id = start_image_to_video(job["image_url"], effective_prompt)
        update_job_prediction(job_id, str(g.user_id), prediction_id)
    except Exception as e:
        return jsonify({"error": "Failed to start job", "message": str(e)}), 500
    response = {
        "job_id": job_id,
        "prediction_id": prediction_id,
        "status": "processing",
        "used_prompt": effective_prompt,
    }
    if agent_outputs:
        response["agent_outputs"] = agent_outputs
    return jsonify(response)


@api_bp.post("/api/agents/generate")
@require_auth
def generate_agents():
    """POST /api/agents/generate: generate hook script and story prompt from user prompt."""
    data = request.get_json(silent=True) or {}
    user_prompt = (data.get("prompt") or "").strip()
    image_url = (data.get("image_url") or "").strip()
    tone = (data.get("tone") or "conversational").strip()
    duration_target_sec = data.get("duration_target_sec", 5)
    if not user_prompt:
        return jsonify({"error": "Missing 'prompt'"}), 400
    try:
        outputs = generate_ad_agents(
            user_prompt=user_prompt,
            image_url=image_url,
            tone=tone,
            duration_target_sec=duration_target_sec,
        )
    except Exception as e:
        return jsonify({"error": "Agent generation failed", "message": str(e)}), 500
    return jsonify(outputs)


@api_bp.post("/api/jobs/<job_id>/agents")
@require_auth
def generate_job_agents(job_id: str):
    """POST /api/jobs/<job_id>/agents: generate hook/story outputs for an existing job."""
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job_id"}), 400
    job = get_job(job_id, str(g.user_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404
    data = request.get_json(silent=True) or {}
    prompt_override = (data.get("prompt_override") or "").strip()
    tone = (data.get("tone") or "conversational").strip()
    duration_target_sec = data.get("duration_target_sec", 5)
    user_prompt = prompt_override or (job.get("prompt") or "").strip()
    if not user_prompt:
        return jsonify({"error": "Job has no prompt and no prompt_override provided"}), 400
    try:
        outputs = generate_ad_agents(
            user_prompt=user_prompt,
            image_url=job.get("image_url") or "",
            tone=tone,
            duration_target_sec=duration_target_sec,
        )
    except Exception as e:
        return jsonify({"error": "Agent generation failed", "message": str(e)}), 500
    return jsonify({"job_id": job_id, "agent_outputs": outputs})


@api_bp.post("/api/jobs/<job_id>/audio")
@require_auth
def generate_job_audio(job_id: str):
    """
    POST /api/jobs/<job_id>/audio: generate TTS audio using Replicate elevenlabs/v3 and persist to storage.
    """
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job_id"}), 400
    job = get_job(job_id, str(g.user_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    voice_raw = (data.get("voice") or "").strip()
    voice = voice_raw or None
    language_code = (data.get("language_code") or "").strip() or None
    use_agents = _as_bool(data.get("use_agents"), False)

    if voice_raw:
        try:
            validate_voice_or_raise(voice_raw)
        except ValueError as e:
            return jsonify({"error": "Invalid voice", "message": str(e)}), 400

    agent_outputs = None
    if not text and use_agents:
        source_prompt = (data.get("prompt_override") or "").strip() or (job.get("prompt") or "").strip()
        if not source_prompt:
            return jsonify({"error": "Missing 'text' and no prompt available to generate script"}), 400
        try:
            agent_outputs = generate_ad_agents(
                user_prompt=source_prompt,
                image_url=job.get("image_url") or "",
                tone=(data.get("tone") or "conversational").strip(),
                duration_target_sec=data.get("duration_target_sec", 5),
            )
            text = (((agent_outputs.get("script_writer") or {}).get("hook_text")) or "").strip()
        except Exception as e:
            return jsonify({"error": "Agent generation failed", "message": str(e)}), 500

    if not text:
        return jsonify({"error": "Missing 'text'"}), 400

    try:
        replicate_audio_url = generate_tts_audio(
            prompt=text,
            voice=voice,
            language_code=language_code,
            speed=_as_float(data.get("speed")),
            stability=_as_float(data.get("stability")),
            similarity_boost=_as_float(data.get("similarity_boost")),
            style=_as_float(data.get("style")),
        )
        audio_url = persist_replicate_audio(replicate_audio_url, job_id)
    except Exception as e:
        return jsonify({"error": "Audio generation failed", "message": str(e)}), 500

    response = {
        "job_id": job_id,
        "text": text,
        "voice": resolve_supported_voice(voice_raw or None)["name"],
        "replicate_audio_url": replicate_audio_url,
        "audio_url": audio_url,
        "status": "succeeded",
    }
    if agent_outputs:
        response["agent_outputs"] = agent_outputs
    return jsonify(response)


@api_bp.post("/api/jobs/<job_id>/start-full")
@require_auth
def start_full_job(job_id: str):
    """
    POST /api/jobs/<job_id>/start-full:
    Full pipeline orchestration:
    script/story -> tts audio -> ugc hook video -> product video -> stitch final video.
    """
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job_id"}), 400

    job = get_job(job_id, str(g.user_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] == "processing":
        return jsonify({"error": "Job already processing", "status": job["status"]}), 400

    data = request.get_json(silent=True) or {}
    existing_manifest = get_pipeline_manifest(job_id) or {}
    manifest_inputs = (existing_manifest.get("inputs") or {}) if isinstance(existing_manifest, dict) else {}

    raw_prompt = (data.get("prompt_override") or "").strip() or (job.get("prompt") or "").strip()
    voice_raw = (data.get("voice") or "").strip() or (manifest_inputs.get("voice") or "").strip()
    if voice_raw:
        try:
            validate_voice_or_raise(voice_raw)
        except ValueError as e:
            return jsonify({"error": "Invalid voice", "message": str(e)}), 400
    voice = resolve_supported_voice(voice_raw or None)["name"]
    product_info = data.get("product_info")
    if product_info is None:
        product_info = manifest_inputs.get("product_info")

    actor_image_url = (data.get("actor_image_url") or "").strip() or (manifest_inputs.get("actor_image_url") or "")
    body_product_images = data.get("product_image_urls")
    product_image_urls = []
    if isinstance(body_product_images, list):
        product_image_urls = [str(u).strip() for u in body_product_images if str(u).strip()]
    if not product_image_urls:
        product_image_urls = [
            str(u).strip()
            for u in (manifest_inputs.get("product_image_urls") or [])
            if str(u).strip()
        ]
    if not product_image_urls and job.get("image_url"):
        product_image_urls = [job["image_url"]]

    if not raw_prompt:
        return jsonify({"error": "Missing prompt. Provide prompt_override or upload with prompt"}), 400
    if not actor_image_url:
        return jsonify({"error": "Missing actor_image_url"}), 400
    if not product_image_urls:
        return jsonify({"error": "Missing product_image_urls"}), 400

    use_agents = _as_bool(data.get("use_agents"), True)
    tone = (data.get("tone") or "conversational").strip()
    duration_target_sec = data.get("duration_target_sec", 5)
    source_prompt = _build_agent_prompt(raw_prompt, product_info)

    artifacts = {}
    agent_outputs = None
    hook_text = (data.get("hook_text") or "").strip()
    story_prompt = (data.get("story_prompt") or "").strip()

    try:
        update_job_status(job_id, str(g.user_id), "processing")

        if use_agents:
            agent_outputs = generate_ad_agents(
                user_prompt=source_prompt,
                image_url=product_image_urls[0],
                tone=tone,
                duration_target_sec=duration_target_sec,
            )
            hook_text = hook_text or (((agent_outputs.get("script_writer") or {}).get("hook_text")) or "").strip()
            story_prompt = story_prompt or (((agent_outputs.get("story_writer") or {}).get("video_prompt")) or "").strip()

        if not hook_text:
            hook_text = source_prompt
        if not story_prompt:
            story_prompt = source_prompt

        replicate_audio_url = generate_tts_audio(
            prompt=hook_text,
            voice=voice,
            language_code=(data.get("language_code") or "").strip() or None,
            speed=_as_float(data.get("speed")),
            stability=_as_float(data.get("stability")),
            similarity_boost=_as_float(data.get("similarity_boost")),
            style=_as_float(data.get("style")),
        )
        audio_url = persist_replicate_audio(replicate_audio_url, job_id, variant="hook")
        artifacts["audio"] = {
            "replicate_url": replicate_audio_url,
            "storage_url": audio_url,
        }

        ugc_prompt = (
            (data.get("ugc_prompt") or "").strip()
            or "Generate a realistic UGC talking-head clip synced to the provided voice audio."
        )
        replicate_hook_video_url = generate_ugc_hook_video(actor_image_url, audio_url, prompt=ugc_prompt)
        hook_video_url = persist_replicate_video(replicate_hook_video_url, job_id, variant="ugc-hook")
        artifacts["ugc_hook_video"] = {
            "replicate_url": replicate_hook_video_url,
            "storage_url": hook_video_url,
        }

        replicate_product_video_url = run_image_to_video(product_image_urls[0], story_prompt)
        product_video_url = persist_replicate_video(replicate_product_video_url, job_id, variant="product")
        artifacts["product_video"] = {
            "replicate_url": replicate_product_video_url,
            "storage_url": product_video_url,
        }

        # Merge order is intentional: UGC hook first, product video second.
        replicate_final_video_url = stitch_videos([hook_video_url, product_video_url])
        final_video_url = persist_replicate_video(replicate_final_video_url, job_id)
        artifacts["final_video"] = {
            "replicate_url": replicate_final_video_url,
            "storage_url": final_video_url,
        }

        update_job_result(job_id, str(g.user_id), final_video_url, "succeeded")
        manifest = {
            "job_id": job_id,
            "user_id": str(g.user_id),
            "status": "succeeded",
            "inputs": {
                "prompt": raw_prompt,
                "source_prompt": source_prompt,
                "tone": tone,
                "duration_target_sec": duration_target_sec,
                "voice": voice,
                "product_info": product_info,
                "actor_image_url": actor_image_url,
                "product_image_urls": product_image_urls,
            },
            "agent_outputs": agent_outputs,
            "artifacts": artifacts,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_url = save_pipeline_manifest(job_id, manifest)
    except Exception as e:
        update_job_result(job_id, str(g.user_id), None, "failed")
        fail_manifest = {
            "job_id": job_id,
            "user_id": str(g.user_id),
            "status": "failed",
            "error": str(e),
            "inputs": {
                "prompt": raw_prompt,
                "source_prompt": source_prompt,
                "tone": tone,
                "duration_target_sec": duration_target_sec,
                "voice": voice,
                "product_info": product_info,
                "actor_image_url": actor_image_url,
                "product_image_urls": product_image_urls,
            },
            "agent_outputs": agent_outputs,
            "artifacts": artifacts,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        save_pipeline_manifest(job_id, fail_manifest)
        return jsonify({"error": "Full pipeline failed", "message": str(e), "artifacts": artifacts}), 500

    response = {
        "job_id": job_id,
        "status": "succeeded",
        "output_video_url": final_video_url,
        "manifest_url": manifest_url,
        "artifacts": artifacts,
    }
    if agent_outputs:
        response["agent_outputs"] = agent_outputs
    return jsonify(response)


@api_bp.get("/api/jobs/<job_id>/pipeline")
@require_auth
def get_job_pipeline(job_id: str):
    """GET /api/jobs/<job_id>/pipeline: return stored full-pipeline manifest/artifacts."""
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job_id"}), 400
    job = get_job(job_id, str(g.user_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404
    manifest = get_pipeline_manifest(job_id)
    if not manifest:
        return jsonify({"error": "Pipeline manifest not found"}), 404
    return jsonify({"job_id": job_id, "pipeline": manifest})


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
                # Persist to our storage so link doesn't expire after 1h
                try:
                    permanent_url = persist_replicate_video(output_url, job_id)
                    update_job_result(job_id, str(g.user_id), permanent_url, "succeeded")
                except Exception:
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
                try:
                    permanent_url = persist_replicate_video(output_url, job_id)
                    update_job_result(job_id, str(g.user_id), permanent_url, "succeeded")
                except Exception:
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

import uuid
import json
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from ad_agents import generate_ad_agents
from auth import create_user, require_auth, verify_user, issue_jwt
from openapi_spec import build_openapi_spec
from supabase_client import (
    upload_product_image,
    upload_actor_image,
    create_job,
    get_job,
    list_jobs,
    persist_replicate_video,
    persist_replicate_audio,
    persist_replicate_actor_image,
    save_pipeline_manifest,
    get_pipeline_manifest,
    update_job_prediction,
    update_job_result,
    update_job_status,
    update_job_actor_variant,
    create_actor,
    get_actor,
    list_actors,
    update_actor_status,
    create_actor_variant,
    get_actor_variant,
    list_actor_variants,
    get_primary_actor_variant,
    update_actor_variant,
    set_primary_actor_variant,
)
from replicate_client import (
    start_image_to_video,
    get_prediction,
    generate_tts_audio,
    get_supported_tts_voices,
    generate_ugc_hook_video,
    run_image_to_video,
    stitch_videos,
    generate_actor_images,
)
from elevenlabs_voices import validate_voice_or_raise, resolve_supported_voice

api_bp = Blueprint("api", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_ACTOR_AGE_BANDS = {"18-24", "25-34", "35-44", "45-54", "55+"}
SWAGGER_UI_VERSION = "5.29.1"


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


def _stringify_actor_traits(traits) -> str:
    if isinstance(traits, str):
        return traits.strip()
    if isinstance(traits, list):
        parts = [str(item).strip() for item in traits if str(item).strip()]
        return ", ".join(parts)
    if isinstance(traits, dict):
        parts = []
        for key, value in traits.items():
            label = str(key).replace("_", " ").strip()
            if isinstance(value, list):
                value_text = ", ".join(str(item).strip() for item in value if str(item).strip())
            else:
                value_text = str(value).strip()
            if label and value_text:
                parts.append(f"{label}: {value_text}")
        return "; ".join(parts)
    return ""


def _build_actor_prompt(
    *,
    age_band: str,
    ethnicity: str,
    gender_presentation: str,
    traits,
    prompt_override: str = "",
) -> str:
    override = (prompt_override or "").strip()
    if override:
        return override

    details = [
        "Create a photorealistic chest-up portrait of a single adult synthetic actor for UGC advertising.",
        f"Age band: {age_band}.",
        f"Ethnicity: {ethnicity}.",
    ]
    if gender_presentation:
        details.append(f"Gender presentation: {gender_presentation}.")

    traits_text = _stringify_actor_traits(traits)
    if traits_text:
        details.append(f"Additional traits: {traits_text}.")

    details.extend([
        "Use natural skin texture, realistic lighting, centered framing, and a simple uncluttered background.",
        "The actor should look like a modern creator who could appear in a paid social ad.",
        "Keep the face fully visible with no hats, sunglasses, text overlays, watermarks, or extra people in frame.",
        "This must be an original person and must not resemble a celebrity, influencer, or public figure.",
    ])
    return " ".join(details)


def _build_actor_variant_prompt(base_prompt: str, variation_notes: str = "") -> str:
    prompt = (base_prompt or "").strip()
    notes = (variation_notes or "").strip()
    suffix = (
        "Keep the same person and facial identity as the reference image while creating a fresh portrait variation "
        "with slightly different pose, expression, framing, or wardrobe details."
    )
    if notes:
        suffix = f"{suffix} Variation request: {notes}."
    return f"{prompt}\n\n{suffix}".strip()


def _serialize_actor(actor: dict, variants: list[dict] | None = None) -> dict:
    actor_data = dict(actor)
    variant_rows = variants
    if variant_rows is None:
        variant_rows = list_actor_variants(actor["id"], actor["user_id"])
    primary_variant = next((variant for variant in variant_rows if variant.get("is_primary")), None)
    if primary_variant is None:
        primary_variant = get_primary_actor_variant(actor["id"], actor["user_id"])
    actor_data["primary_variant"] = primary_variant
    actor_data["variant_count"] = len(variant_rows)
    if variants is not None:
        actor_data["variants"] = variant_rows
    return actor_data


def _persist_actor_generation_outputs(
    *,
    actor_id: str,
    user_id: str,
    prompt: str,
    generation_result: dict,
    make_first_primary: bool,
) -> tuple[list[dict], list[str]]:
    created_variants = []
    warnings = []
    image_urls = [
        str(url).strip()
        for url in (generation_result.get("images") or [])
        if str(url).strip()
    ]
    model_name = str(generation_result.get("model") or "").strip() or None

    for index, replicate_image_url in enumerate(image_urls):
        metadata = {
            "replicate_url": replicate_image_url,
            "generation_index": index + 1,
        }
        variant = create_actor_variant(
            actor_id,
            user_id,
            status="generating",
            prompt=prompt,
            replicate_model=model_name,
            metadata=metadata,
            is_primary=make_first_primary and index == 0,
        )
        try:
            image_url = persist_replicate_actor_image(replicate_image_url, actor_id, variant["id"])
            update_actor_variant(
                variant["id"],
                user_id,
                {
                    "status": "ready",
                    "image_url": image_url,
                    "thumbnail_url": image_url,
                    "metadata": metadata,
                },
            )
            stored_variant = get_actor_variant(variant["id"], user_id)
            if stored_variant:
                created_variants.append(stored_variant)
        except Exception as e:
            update_actor_variant(
                variant["id"],
                user_id,
                {
                    "status": "failed",
                    "is_primary": False,
                    "metadata": {**metadata, "error": str(e)},
                },
            )
            warnings.append(str(e))

    return created_variants, warnings


def _normalize_uuid_param(value) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(uuid.UUID(str(value)))


def _artifact_storage_url(artifact) -> str:
    if not isinstance(artifact, dict):
        return ""
    return str(artifact.get("storage_url") or "").strip()


def _save_pipeline_progress(
    *,
    job_id: str,
    user_id: str,
    status: str,
    current_stage: str,
    inputs: dict,
    agent_outputs,
    artifacts: dict,
    error: str | None = None,
) -> str:
    manifest = {
        "job_id": job_id,
        "user_id": user_id,
        "status": status,
        "current_stage": current_stage,
        "inputs": inputs,
        "agent_outputs": agent_outputs,
        "artifacts": artifacts,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if error:
        manifest["error"] = error
    return save_pipeline_manifest(job_id, manifest)


def _swagger_ui_html() -> str:
    css_url = f"https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/{SWAGGER_UI_VERSION}/swagger-ui.min.css"
    bundle_url = f"https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/{SWAGGER_UI_VERSION}/swagger-ui-bundle.min.js"
    preset_url = (
        f"https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/{SWAGGER_UI_VERSION}/swagger-ui-standalone-preset.min.js"
    )
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Adbase API Docs</title>
        <link rel="stylesheet" href="{css_url}">
        <style>
            html {{
                box-sizing: border-box;
                overflow-y: scroll;
            }}
            *, *:before, *:after {{
                box-sizing: inherit;
            }}
            body {{
                margin: 0;
                background: #f7f9fc;
            }}
            .topbar {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 14px 20px;
                background: #0f172a;
                color: #f8fafc;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }}
            .topbar a {{
                color: #93c5fd;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <strong>Adbase Backend API Docs</strong>
            <a href="/openapi.json" target="_blank" rel="noreferrer">OpenAPI JSON</a>
        </div>
        <div id="swagger-ui"></div>
        <script src="{bundle_url}"></script>
        <script src="{preset_url}"></script>
        <script>
            window.onload = function() {{
                window.ui = SwaggerUIBundle({{
                    url: "/openapi.json",
                    dom_id: "#swagger-ui",
                    deepLinking: true,
                    docExpansion: "list",
                    persistAuthorization: true,
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIStandalonePreset
                    ],
                    layout: "StandaloneLayout"
                }});
            }};
        </script>
    </body>
    </html>
    """


# --- Auth ---


@api_bp.post("/api/auth/register")
def register():
    """Create a user and immediately issue the same JWT used by the login endpoint."""
    data = request.get_json(silent=True) or {}
    username_raw = data.get("username")
    password_raw = data.get("password")
    if not isinstance(username_raw, str) or not isinstance(password_raw, str):
        return jsonify({"error": "Username and password must be strings"}), 400
    username = username_raw.strip()
    password = password_raw
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    try:
        user_id = create_user(username, password)
    except Exception as e:
        # PostgreSQL unique_violation. Supabase/PostgREST exceptions expose this
        # either as a code attribute or in their serialized error payload.
        if getattr(e, "code", None) == "23505" or "23505" in str(e):
            return jsonify({"error": "Username already exists"}), 409
        return jsonify({"error": "Failed to create user"}), 500

    token = issue_jwt(user_id)
    return jsonify({"token": token}), 201


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


@api_bp.get("/openapi.json")
def openapi_json():
    """GET /openapi.json: machine-readable OpenAPI document for the backend."""
    return jsonify(build_openapi_spec(request.url_root))


@api_bp.get("/docs")
def swagger_docs():
    """GET /docs: interactive Swagger UI for the OpenAPI document."""
    return _swagger_ui_html()


# --- Actors (all require Bearer token) ---


@api_bp.get("/api/actors")
@require_auth
def list_user_actors():
    """GET /api/actors: list current user's actor library."""
    try:
        limit = min(int(request.args.get("limit", 50)), 100)
    except (TypeError, ValueError):
        limit = 50
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except (TypeError, ValueError):
        offset = 0

    user_id = str(g.user_id)
    actors = list_actors(user_id, limit=limit, offset=offset)
    payload = [_serialize_actor(actor) for actor in actors]
    return jsonify({"actors": payload, "total": len(payload)})


@api_bp.get("/api/actors/<uuid:actor_id>")
@require_auth
def get_user_actor(actor_id):
    """GET /api/actors/<actor_id>: return one actor and its variants."""
    actor_id = _normalize_uuid_param(actor_id)

    user_id = str(g.user_id)
    actor = get_actor(actor_id, user_id)
    if not actor:
        return jsonify({"error": "Actor not found"}), 404

    variants = list_actor_variants(actor_id, user_id)
    return jsonify({"actor": _serialize_actor(actor, variants=variants)})


@api_bp.post("/api/actors/generate")
@require_auth
def generate_actor():
    """POST /api/actors/generate: create a reusable synthetic actor and generate still variants."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip() or None
    age_band = (data.get("age_band") or "").strip()
    ethnicity = (data.get("ethnicity") or "").strip()
    gender_presentation = (data.get("gender_presentation") or "").strip()
    traits = data.get("traits")
    prompt_override = (data.get("prompt_override") or "").strip()
    model_override = (data.get("model") or "").strip() or None
    image_count = data.get("image_count")

    if age_band not in ALLOWED_ACTOR_AGE_BANDS:
        return jsonify({
            "error": "Invalid age_band",
            "allowed_age_bands": sorted(ALLOWED_ACTOR_AGE_BANDS),
        }), 400
    if not ethnicity:
        return jsonify({"error": "Missing 'ethnicity'"}), 400

    prompt = _build_actor_prompt(
        age_band=age_band,
        ethnicity=ethnicity,
        gender_presentation=gender_presentation,
        traits=traits,
        prompt_override=prompt_override,
    )

    user_id = str(g.user_id)
    actor = create_actor(
        user_id,
        name=name,
        age_band=age_band,
        ethnicity=ethnicity,
        gender_presentation=gender_presentation or None,
        prompt=prompt,
        attributes={"traits": traits} if traits is not None else {},
        status="generating",
    )

    try:
        generation_result = generate_actor_images(
            prompt,
            image_count=image_count,
            model=model_override,
        )
        created_variants, warnings = _persist_actor_generation_outputs(
            actor_id=actor["id"],
            user_id=user_id,
            prompt=prompt,
            generation_result=generation_result,
            make_first_primary=True,
        )
        if not created_variants:
            update_actor_status(actor["id"], user_id, "failed")
            return jsonify({"error": "Actor generation failed", "warnings": warnings}), 500

        if not any(variant.get("is_primary") for variant in created_variants):
            set_primary_actor_variant(actor["id"], user_id, created_variants[0]["id"])
            created_variants = list_actor_variants(actor["id"], user_id)

        update_actor_status(actor["id"], user_id, "ready")
        actor = get_actor(actor["id"], user_id) or actor
        response = {
            "actor": _serialize_actor(actor, variants=created_variants),
            "generation_model": generation_result.get("model"),
        }
        if warnings:
            response["warnings"] = warnings
        return jsonify(response), 201
    except Exception as e:
        update_actor_status(actor["id"], user_id, "failed")
        return jsonify({"error": "Actor generation failed", "message": str(e)}), 500


@api_bp.post("/api/actors/<uuid:actor_id>/variants")
@require_auth
def generate_actor_variants(actor_id):
    """POST /api/actors/<actor_id>/variants: create more still variants for an existing actor."""
    actor_id = _normalize_uuid_param(actor_id)

    user_id = str(g.user_id)
    actor = get_actor(actor_id, user_id)
    if not actor:
        return jsonify({"error": "Actor not found"}), 404

    primary_variant = get_primary_actor_variant(actor_id, user_id)
    if not primary_variant or not primary_variant.get("image_url"):
        return jsonify({"error": "Actor has no primary variant to use as reference"}), 400

    data = request.get_json(silent=True) or {}
    model_override = (data.get("model") or "").strip() or None
    image_count = data.get("image_count")
    variation_notes = (data.get("variation_prompt") or "").strip()
    prompt_override = (data.get("prompt_override") or "").strip()
    prompt = prompt_override or _build_actor_variant_prompt(actor.get("prompt") or "", variation_notes)

    try:
        generation_result = generate_actor_images(
            prompt,
            image_count=image_count,
            model=model_override,
            reference_image_urls=[primary_variant["image_url"]],
        )
        created_variants, warnings = _persist_actor_generation_outputs(
            actor_id=actor_id,
            user_id=user_id,
            prompt=prompt,
            generation_result=generation_result,
            make_first_primary=False,
        )
        if not created_variants:
            return jsonify({"error": "Actor variant generation failed", "warnings": warnings}), 500

        actor = get_actor(actor_id, user_id) or actor
        response = {
            "actor": _serialize_actor(actor, variants=list_actor_variants(actor_id, user_id)),
            "created_variants": created_variants,
            "generation_model": generation_result.get("model"),
        }
        if warnings:
            response["warnings"] = warnings
        return jsonify(response), 201
    except Exception as e:
        return jsonify({"error": "Actor variant generation failed", "message": str(e)}), 500


@api_bp.post("/api/actors/<uuid:actor_id>/select-primary")
@require_auth
def select_primary_actor(actor_id):
    """POST /api/actors/<actor_id>/select-primary: choose which variant should be the default actor image."""
    actor_id = _normalize_uuid_param(actor_id)

    user_id = str(g.user_id)
    actor = get_actor(actor_id, user_id)
    if not actor:
        return jsonify({"error": "Actor not found"}), 404

    data = request.get_json(silent=True) or {}
    actor_variant_id = (data.get("actor_variant_id") or "").strip()
    try:
        uuid.UUID(actor_variant_id)
    except ValueError:
        return jsonify({"error": "Invalid actor_variant_id"}), 400

    actor_variant = get_actor_variant(actor_variant_id, user_id)
    if (
        not actor_variant
        or actor_variant.get("actor_id") != actor_id
        or actor_variant.get("status") != "ready"
        or not actor_variant.get("image_url")
    ):
        return jsonify({"error": "Actor variant not found"}), 404

    set_primary_actor_variant(actor_id, user_id, actor_variant_id)
    actor = get_actor(actor_id, user_id) or actor
    variants = list_actor_variants(actor_id, user_id)
    return jsonify({"actor": _serialize_actor(actor, variants=variants)})


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
    actor_variant_id = (request.form.get("actor_variant_id") or "").strip()

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
        if actor_variant_id:
            try:
                uuid.UUID(actor_variant_id)
            except ValueError:
                return jsonify({"error": "Invalid actor_variant_id"}), 400
            actor_variant = get_actor_variant(actor_variant_id, str(g.user_id))
            if (
                not actor_variant
                or actor_variant.get("status") != "ready"
                or not actor_variant.get("image_url")
            ):
                return jsonify({"error": "Actor variant not found"}), 404
            actor_image_url = actor_variant["image_url"]
        elif actor_file and actor_file.filename:
            if actor_file.content_type and actor_file.content_type not in ALLOWED_IMAGE_EXTENSIONS:
                return jsonify({"error": f"Invalid actor image type: {actor_file.content_type}"}), 400
            actor_bytes = actor_file.read()
            actor_image_url = upload_actor_image(
                actor_bytes,
                actor_file.filename,
                actor_file.content_type or "image/jpeg",
            )

        job = create_job(str(g.user_id), product_image_urls[0], prompt, actor_variant_id=actor_variant_id or None)
        manifest = {
            "job_id": job["id"],
            "user_id": str(g.user_id),
            "inputs": {
                "prompt": prompt,
                "voice": voice or None,
                "product_info": product_info,
                "actor_variant_id": actor_variant_id or None,
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
        "actor_variant_id": actor_variant_id or None,
        "actor_image_url": actor_image_url,
        "product_image_urls": product_image_urls,
        "manifest_url": manifest_url,
    }), 201


@api_bp.post("/api/jobs/<uuid:job_id>/start")
@require_auth
def start_job(job_id):
    """POST /api/jobs/<job_id>/start: start Replicate prediction for a draft job."""
    job_id = _normalize_uuid_param(job_id)
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


@api_bp.post("/api/jobs/<uuid:job_id>/agents")
@require_auth
def generate_job_agents(job_id):
    """POST /api/jobs/<job_id>/agents: generate hook/story outputs for an existing job."""
    job_id = _normalize_uuid_param(job_id)
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


@api_bp.post("/api/jobs/<uuid:job_id>/audio")
@require_auth
def generate_job_audio(job_id):
    """
    POST /api/jobs/<job_id>/audio: generate TTS audio using Replicate elevenlabs/v3 and persist to storage.
    """
    job_id = _normalize_uuid_param(job_id)
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


@api_bp.post("/api/jobs/<uuid:job_id>/start-full")
@require_auth
def start_full_job(job_id):
    """
    POST /api/jobs/<job_id>/start-full:
    Full pipeline orchestration:
    script/story -> tts audio -> ugc hook video -> product video -> stitch final video.
    """
    job_id = _normalize_uuid_param(job_id)

    job = get_job(job_id, str(g.user_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json(silent=True) or {}
    force_restart = _as_bool(data.get("force_restart"), False)
    resume_pipeline = _as_bool(data.get("resume"), True)

    if job["status"] == "processing" and not force_restart:
        return jsonify({
            "error": "Job already processing",
            "status": job["status"],
            "message": (
                "If the earlier request timed out but you want to continue from saved artifacts, "
                "call this endpoint again with {\"force_restart\": true, \"resume\": true}."
            ),
        }), 400

    existing_manifest = get_pipeline_manifest(job_id) or {}
    if not resume_pipeline or not isinstance(existing_manifest, dict):
        existing_manifest = {}
    manifest_inputs = (existing_manifest.get("inputs") or {}) if isinstance(existing_manifest, dict) else {}
    existing_artifacts = (
        dict(existing_manifest.get("artifacts") or {})
        if isinstance(existing_manifest.get("artifacts"), dict)
        else {}
    )

    raw_prompt = (
        (data.get("prompt_override") or "").strip()
        or (manifest_inputs.get("prompt") or "").strip()
        or (job.get("prompt") or "").strip()
    )
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

    actor_variant_id = (data.get("actor_variant_id") or "").strip()
    if not actor_variant_id:
        actor_variant_id = str(job.get("actor_variant_id") or "").strip()
    if not actor_variant_id:
        actor_variant_id = str(manifest_inputs.get("actor_variant_id") or "").strip()

    actor_variant = None
    if actor_variant_id:
        try:
            uuid.UUID(actor_variant_id)
        except ValueError:
            return jsonify({"error": "Invalid actor_variant_id"}), 400
        actor_variant = get_actor_variant(actor_variant_id, str(g.user_id))
        if (
            not actor_variant
            or actor_variant.get("status") != "ready"
            or not actor_variant.get("image_url")
        ):
            return jsonify({"error": "Actor variant not found"}), 404

    actor_image_url = ""
    if actor_variant:
        actor_image_url = actor_variant["image_url"]
    else:
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

    artifacts = dict(existing_artifacts)
    agent_outputs = existing_manifest.get("agent_outputs") if isinstance(existing_manifest, dict) else None
    hook_text = (data.get("hook_text") or "").strip() or (manifest_inputs.get("hook_text") or "").strip()
    story_prompt = (data.get("story_prompt") or "").strip() or (manifest_inputs.get("story_prompt") or "").strip()
    ugc_prompt = (
        (data.get("ugc_prompt") or "").strip()
        or (manifest_inputs.get("ugc_prompt") or "").strip()
        or "Generate a realistic UGC talking-head clip synced to the provided voice audio."
    )
    current_stage = "starting"
    manifest_url = ""

    def _persist_progress(status: str, stage: str, error: str | None = None) -> str:
        nonlocal manifest_url
        manifest_url = _save_pipeline_progress(
            job_id=job_id,
            user_id=str(g.user_id),
            status=status,
            current_stage=stage,
            inputs={
                "prompt": raw_prompt,
                "source_prompt": source_prompt,
                "tone": tone,
                "duration_target_sec": duration_target_sec,
                "voice": voice,
                "product_info": product_info,
                "actor_variant_id": actor_variant_id or None,
                "actor_image_url": actor_image_url,
                "product_image_urls": product_image_urls,
                "hook_text": hook_text or None,
                "story_prompt": story_prompt or None,
                "ugc_prompt": ugc_prompt or None,
            },
            agent_outputs=agent_outputs,
            artifacts=artifacts,
            error=error,
        )
        return manifest_url

    try:
        update_job_status(job_id, str(g.user_id), "processing")
        if actor_variant_id:
            update_job_actor_variant(job_id, str(g.user_id), actor_variant_id)
        _persist_progress("processing", current_stage)

        if use_agents and not agent_outputs:
            current_stage = "agents_generation"
            _persist_progress("processing", current_stage)
            agent_outputs = generate_ad_agents(
                user_prompt=source_prompt,
                image_url=product_image_urls[0],
                tone=tone,
                duration_target_sec=duration_target_sec,
            )
            hook_text = hook_text or (((agent_outputs.get("script_writer") or {}).get("hook_text")) or "").strip()
            story_prompt = story_prompt or (((agent_outputs.get("story_writer") or {}).get("video_prompt")) or "").strip()
            _persist_progress("processing", "agents_completed")

        if not hook_text:
            hook_text = source_prompt
        if not story_prompt:
            story_prompt = source_prompt
        _persist_progress("processing", "prompts_ready")

        audio_artifact = artifacts.get("audio") if isinstance(artifacts.get("audio"), dict) else {}
        audio_url = _artifact_storage_url(audio_artifact)
        if not audio_url:
            current_stage = "tts_audio"
            _persist_progress("processing", current_stage)
            try:
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
            except Exception as e:
                raise RuntimeError(f"[tts_audio] {e}") from e
            artifacts["audio"] = {
                "replicate_url": replicate_audio_url,
                "storage_url": audio_url,
            }
            _persist_progress("processing", "tts_audio_completed")

        hook_artifact = artifacts.get("ugc_hook_video") if isinstance(artifacts.get("ugc_hook_video"), dict) else {}
        hook_video_url = _artifact_storage_url(hook_artifact)
        if not hook_video_url:
            current_stage = "ugc_hook_video"
            _persist_progress("processing", current_stage)
            try:
                replicate_hook_video_url = generate_ugc_hook_video(actor_image_url, audio_url, prompt=ugc_prompt)
                hook_video_url = persist_replicate_video(replicate_hook_video_url, job_id, variant="ugc-hook")
            except Exception as e:
                raise RuntimeError(f"[ugc_hook_video] {e}") from e
            artifacts["ugc_hook_video"] = {
                "replicate_url": replicate_hook_video_url,
                "storage_url": hook_video_url,
            }
            _persist_progress("processing", "ugc_hook_video_completed")

        product_artifact = artifacts.get("product_video") if isinstance(artifacts.get("product_video"), dict) else {}
        product_video_url = _artifact_storage_url(product_artifact)
        if not product_video_url:
            current_stage = "product_video"
            _persist_progress("processing", current_stage)
            try:
                replicate_product_video_url = run_image_to_video(product_image_urls[0], story_prompt)
                product_video_url = persist_replicate_video(replicate_product_video_url, job_id, variant="product")
            except Exception as e:
                raise RuntimeError(f"[product_video] {e}") from e
            artifacts["product_video"] = {
                "replicate_url": replicate_product_video_url,
                "storage_url": product_video_url,
            }
            _persist_progress("processing", "product_video_completed")

        final_artifact = artifacts.get("final_video") if isinstance(artifacts.get("final_video"), dict) else {}
        final_video_url = _artifact_storage_url(final_artifact)
        if not final_video_url:
            current_stage = "video_merge"
            _persist_progress("processing", current_stage)
            try:
                # Merge order is intentional: UGC hook first, product video second.
                replicate_final_video_url = stitch_videos([hook_video_url, product_video_url])
                final_video_url = persist_replicate_video(replicate_final_video_url, job_id)
            except Exception as e:
                raise RuntimeError(f"[video_merge] {e}") from e
            artifacts["final_video"] = {
                "replicate_url": replicate_final_video_url,
                "storage_url": final_video_url,
            }

        update_job_result(job_id, str(g.user_id), final_video_url, "succeeded")
        _persist_progress("succeeded", "completed")
    except Exception as e:
        update_job_result(job_id, str(g.user_id), None, "failed")
        _persist_progress("failed", current_stage, error=str(e))
        return jsonify({
            "error": "Full pipeline failed",
            "message": str(e),
            "current_stage": current_stage,
            "artifacts": artifacts,
            "manifest_url": manifest_url,
        }), 500

    response = {
        "job_id": job_id,
        "status": "succeeded",
        "actor_variant_id": actor_variant_id or None,
        "output_video_url": final_video_url,
        "manifest_url": manifest_url,
        "artifacts": artifacts,
        "resumed": resume_pipeline and bool(existing_artifacts),
    }
    if agent_outputs:
        response["agent_outputs"] = agent_outputs
    return jsonify(response)


@api_bp.get("/api/jobs/<uuid:job_id>/pipeline")
@require_auth
def get_job_pipeline(job_id):
    """GET /api/jobs/<job_id>/pipeline: return stored full-pipeline manifest/artifacts."""
    job_id = _normalize_uuid_param(job_id)
    job = get_job(job_id, str(g.user_id))
    if not job:
        return jsonify({"error": "Job not found"}), 404
    manifest = get_pipeline_manifest(job_id)
    if not manifest:
        return jsonify({"error": "Pipeline manifest not found"}), 404
    return jsonify({"job_id": job_id, "pipeline": manifest})


@api_bp.get("/api/jobs/<uuid:job_id>")
@require_auth
def get_job_status(job_id):
    """GET /api/jobs/<job_id>: return job status; if processing, poll Replicate and update DB."""
    job_id = _normalize_uuid_param(job_id)
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
    manifest = get_pipeline_manifest(job_id) or {}
    response = {
        "job_id": job["id"],
        "status": job["status"],
        "image_url": job.get("image_url"),
        "prompt": job.get("prompt"),
        "actor_variant_id": job.get("actor_variant_id"),
        "replicate_prediction_id": job.get("replicate_prediction_id"),
        "output_video_url": job.get("output_video_url"),
        "created_at": job.get("created_at"),
    }
    if isinstance(manifest, dict) and manifest:
        response["pipeline"] = {
            "status": manifest.get("status"),
            "current_stage": manifest.get("current_stage"),
            "updated_at": manifest.get("updated_at"),
            "error": manifest.get("error"),
            "artifacts": manifest.get("artifacts") or {},
        }
    return jsonify(response)


@api_bp.get("/api/jobs/<uuid:job_id>/result")
@require_auth
def get_job_result(job_id):
    """GET /api/jobs/<job_id>/result: return video URL if succeeded, 202 if still processing."""
    job_id = _normalize_uuid_param(job_id)
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
        manifest = get_pipeline_manifest(job_id) or {}
        response = {"status": "processing", "message": "Video not ready yet"}
        if isinstance(manifest, dict) and manifest:
            response["current_stage"] = manifest.get("current_stage")
            response["artifacts"] = manifest.get("artifacts") or {}
        return jsonify(response), 202
    if job["status"] == "failed":
        manifest = get_pipeline_manifest(job_id) or {}
        response = {"error": "Job failed"}
        if isinstance(manifest, dict) and manifest:
            response["current_stage"] = manifest.get("current_stage")
            response["details"] = manifest.get("error")
            response["artifacts"] = manifest.get("artifacts") or {}
        return jsonify(response), 500
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

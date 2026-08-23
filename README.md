[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fvercel%2Fvercel%2Ftree%2Fmain%2Fexamples%2Fflask&demo-title=Flask%20API&demo-description=Use%20Flask%20API%20on%20Vercel%20with%20Serverless%20Functions%20using%20the%20Python%20Runtime.&demo-url=https%3A%2F%2Fvercel-plus-flask.vercel.app%2F&demo-image=https://assets.vercel.com/image/upload/v1669994600/random/python.png)

# Flask + Vercel

This example shows how to use Flask on Vercel with Serverless Functions using the [Python Runtime](https://vercel.com/docs/concepts/functions/serverless-functions/runtimes/python).

## Demo

https://vercel-plus-flask.vercel.app/

## How it Works

This example uses the Web Server Gateway Interface (WSGI) with Flask to handle requests on Vercel with Serverless Functions.

## Running Locally

```bash
npm i -g vercel
python -m venv .venv
source .venv/bin/activate
uv sync  # or alternatively pip install flask gunicorn
gunicorn main:app
```

Your Flask application is now available at `http://localhost:3000`.

Interactive docs are available at:

- `http://localhost:3000/docs`
- `http://localhost:3000/openapi.json`

## Environment variables

Set these locally (and in Vercel) for auth, Supabase, and Replicate:

- `SUPABASE_URL` – Supabase project URL  
- `SUPABASE_SERVICE_ROLE_KEY` – Supabase service role key  
- `SUPABASE_BUCKET_PRODUCT_IMAGES` – (optional) Storage bucket name, default `product-images`  
- `SUPABASE_BUCKET_VIDEOS` – (optional) Storage bucket for persisted video outputs, default `product-videos`  
- `SUPABASE_BUCKET_AUDIO` – (optional) Storage bucket for persisted audio outputs, default `product-audio`  
- `SUPABASE_BUCKET_ACTORS` – (optional) Storage bucket for reusable actor portraits, default `actor-images`
- `SUPABASE_SAMPLE_VOICES_BASE_URL` – (optional) Public base URL for voice samples, defaulting to the `sample_voices` Supabase bucket
- `REPLICATE_API_TOKEN` – Replicate API token  
- `REPLICATE_IMAGE_TO_VIDEO_VERSION` – (optional) Model, default `google/veo-3.1-fast`  
- `REPLICATE_VIDEO_RESOLUTION` – (optional) `720p` or `1080p`, default `720p`  
- `REPLICATE_VIDEO_DURATION` – (optional) Seconds: `4`, `6`, or `8`, default `8`  
- `REPLICATE_VIDEO_ASPECT_RATIO` – (optional) `16:9` or `9:16`, default `9:16`  
- `REPLICATE_TEXT_MODEL` – (optional) Replicate LLM model for script/story agents, default `google/gemini-2.5-flash`  
- `REPLICATE_TTS_MODEL` – (optional) Replicate TTS model for audio generation, default `elevenlabs/v3`  
- `REPLICATE_TTS_VOICE` – (optional) Default ElevenLabs voice (name or voice_id), default `Rachel`  
- `REPLICATE_TTS_LANGUAGE_CODE` – (optional) Language code for TTS, default `en`  
- `REPLICATE_FABRIC_MODEL` – (optional) UGC talking-head model, default `veed/fabric-1.0`  
- `REPLICATE_FABRIC_RESOLUTION` – (optional) Fabric output resolution (`480p` or `720p`), default `480p`  
- `REPLICATE_FFMPEG_MODEL` – (optional) Stitch model, default `idan054/better-video-merge:6bda9eb61c16dedaa6804792a252cf7a7c260a5c2bf3ac479adab2d3a4e983ad`  
- `REPLICATE_ACTOR_MODEL` – (optional) Actor portrait generation model, default `bytedance/seedream-4.5`
- `REPLICATE_ACTOR_IMAGE_COUNT` – (optional) Default number of actor variants to create, default `4`
- `REPLICATE_ACTOR_IMAGE_WIDTH` – (optional) Actor portrait width in px, default `1536`
- `REPLICATE_ACTOR_IMAGE_HEIGHT` – (optional) Actor portrait height in px, default `2048`
- `JWT_SECRET` – Secret used to sign login JWTs  
- `CORS_ORIGINS` – (optional) Comma-separated allowed origins for CORS; default includes localhost variants, `https://tryadbase.com`, and `https://www.tryadbase.com`. Override to add or change origins.

## API

- **POST /api/auth/login** – Body: `{ "username", "password" }`. Returns `{ "token": "..." }`.  
- **POST /api/auth/register** – Body: `{ "username", "password" }`. Creates the user and returns `{ "token": "..." }` with HTTP 201.
- **GET /docs** – Interactive Swagger UI for the backend.
- **GET /openapi.json** – OpenAPI document for sharing with frontend/QA/integrators.
- **GET /api/actors** – Auth: Bearer. List current user's reusable actor library with the primary variant for each actor.
- **GET /api/actors/<actor_id>** – Auth: Bearer. Return one actor and all generated still variants.
- **POST /api/actors/generate** – Auth: Bearer. Create a synthetic actor from structured attributes and generate reusable still portraits.
  - JSON:
    - `name` (string, optional)
    - `age_band` (required): one of `18-24`, `25-34`, `35-44`, `45-54`, `55+`
    - `ethnicity` (required)
    - `gender_presentation` (optional)
    - `traits` (string, array, or object; optional)
    - `prompt_override` (optional): use your own generation prompt instead of the backend template
    - `model` (optional): override the default actor model for this request
    - `image_count` (optional): number of portrait variants to generate
- **POST /api/actors/<actor_id>/variants** – Auth: Bearer. Generate additional still variants for an existing actor using the primary variant as a reference.
- **POST /api/actors/<actor_id>/select-primary** – Auth: Bearer. JSON `{ "actor_variant_id": "..." }`. Marks one variant as the actor's default image.
- **GET /api/voices/elevenlabs-v3** – Auth: Bearer. Returns the Replicate-allowed ElevenLabs v3 voices with `sample_url` values for selector UI and `default_voice`.
- **POST /api/jobs/upload** – Auth: Bearer token. Form: `image` (file), `prompt` (optional). Returns `job_id`, `image_url`, `status`.  
- **POST /api/jobs/upload-full** – Auth: Bearer token. Multipart form for full flow:
  - `product_images` (one or more files; fallback field `image`)
  - `actor_image` (file, optional but required later for full pipeline when `actor_variant_id` is not used)
  - `actor_variant_id` (text, optional): select a reusable actor from the actor library instead of uploading an actor image
  - `prompt` (text)
  - `voice` (text, optional)
  - `product_info` (JSON string or text, optional)
  - Returns `job_id`, uploaded image URLs, and `manifest_url`.
- **POST /api/jobs/<job_id>/start** – Auth: Bearer. Starts Replicate image-to-video job.  
  - Backward compatible: no body required (uses saved `prompt` exactly like before).
  - Optional JSON body:  
    - `use_agents` (bool): generate hook + story prompt and use story prompt for video generation  
    - `prompt_override` (string): override job prompt for this run only  
    - `tone` (string): tone hint for agent generation (default `conversational`)  
    - `duration_target_sec` (int): hook duration target (default `5`)  
  - Returns `job_id`, `prediction_id`, `status`, `used_prompt`, and optional `agent_outputs`.
- **POST /api/agents/generate** – Auth: Bearer. JSON `{ prompt, image_url?, tone?, duration_target_sec? }`. Returns:
  - `script_writer` (UGC hook script output)
  - `story_writer` (video generation prompt output)
  - `meta` (provider/model info)
- **POST /api/jobs/<job_id>/agents** – Auth: Bearer. Generate agent outputs based on existing job prompt/image. Optional `prompt_override`, `tone`, `duration_target_sec`.
- **POST /api/jobs/<job_id>/audio** – Auth: Bearer. Generate TTS audio via Replicate `elevenlabs/v3`, then persist to Supabase Storage and return permanent URL.
  - JSON:
    - `text` (string, optional if `use_agents=true`)
    - `voice` (string, optional; pass supported `name` from voices API; legacy IDs for overlapping voices are also accepted)
    - `language_code` (string, optional)
    - `speed`, `stability`, `similarity_boost`, `style` (number, optional)
    - `use_agents` (bool, optional): derive `text` from ScriptWriter hook
    - `prompt_override`, `tone`, `duration_target_sec` (optional): used only with `use_agents=true`
  - Returns `audio_url` (persisted), `replicate_audio_url`, `text`, and optional `agent_outputs`.
- **POST /api/jobs/<job_id>/start-full** – Auth: Bearer. Run full ad pipeline:
  1. ScriptWriter + StoryWriter agents
  2. ElevenLabs v3 TTS on Replicate (persist audio)
  3. Fabric UGC hook generation from actor image + audio (persist hook video)
  4. Veo product video generation from story prompt + product image (persist product video)
  5. Video merge of hook + product video using `idan054/better-video-merge:6bda9eb61c16dedaa6804792a252cf7a7c260a5c2bf3ac479adab2d3a4e983ad` (persist final video and update `jobs.output_video_url`)
  - Optional JSON:
    - `prompt_override`, `product_info`
    - `actor_variant_id`, `actor_image_url`, `product_image_urls`
    - `voice` (supported name), `language_code`, `speed`, `stability`, `similarity_boost`, `style`
    - `use_agents` (default `true`), `tone`, `duration_target_sec`
    - `hook_text`, `story_prompt`, `ugc_prompt` (manual overrides)
    - `resume` (default `true`): reuse completed stage artifacts from the saved manifest when retrying a partial run
    - `force_restart` (default `false`): allow restarting a job that is stuck in `processing`; combine with `resume=true` to continue from saved artifacts
  - Returns `output_video_url`, per-step artifact URLs, and `manifest_url`.
  - Merge stage always enforces `keep_audio=true`.
- **GET /api/jobs/<job_id>/pipeline** – Auth: Bearer. Returns stored pipeline manifest/artifacts.
- **GET /api/jobs** – Auth: Bearer. List current user's generations (newest first). Query: `limit` (default 50, max 100), `offset` (default 0). Returns `{ "jobs": [...], "total": N }` with `id`, `status`, `image_url`, `prompt`, `actor_variant_id`, `output_video_url`, `created_at` per job.  
- **GET /api/jobs/<job_id>** – Auth: Bearer. Returns job status, `actor_variant_id`, and, when available, `pipeline.current_stage`, saved artifacts, and `output_video_url`.  
- **GET /api/jobs/<job_id>/result** – Auth: Bearer. Returns `{ "output_video_url": "..." }` when ready, or 202 while processing with the current pipeline stage when available.  

## One-Click Deploy

Deploy the example using [Vercel](https://vercel.com?utm_source=github&utm_medium=readme&utm_campaign=vercel-examples):

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fvercel%2Fvercel%2Ftree%2Fmain%2Fexamples%2Fflask&demo-title=Flask%20API&demo-description=Use%20Flask%20API%20on%20Vercel%20with%20Serverless%20Functions%20using%20the%20Python%20Runtime.&demo-url=https%3A%2F%2Fvercel-plus-flask.vercel.app%2F&demo-image=https://assets.vercel.com/image/upload/v1669994600/random/python.png)

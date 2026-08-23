"""Load configuration from environment variables."""
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_BUCKET_PRODUCT_IMAGES = os.environ.get("SUPABASE_BUCKET_PRODUCT_IMAGES", "product-images")
SUPABASE_BUCKET_VIDEOS = os.environ.get("SUPABASE_BUCKET_VIDEOS", "product-videos")
SUPABASE_BUCKET_AUDIO = os.environ.get("SUPABASE_BUCKET_AUDIO", "product-audio")
SUPABASE_BUCKET_ACTORS = os.environ.get("SUPABASE_BUCKET_ACTORS", "actor-images")
SUPABASE_SAMPLE_VOICES_BASE_URL = os.environ.get(
    "SUPABASE_SAMPLE_VOICES_BASE_URL",
    "https://rgyolqumnpuygbbxulqe.supabase.co/storage/v1/object/public/sample_voices",
).strip().rstrip("/")

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "").strip()
# Product image-to-video model (owner/name or owner/name:version).
REPLICATE_IMAGE_TO_VIDEO_VERSION = os.environ.get(
    "REPLICATE_IMAGE_TO_VIDEO_VERSION",
    "google/veo-3.1-lite",
).strip()
# Veo defaults: resolution (720p | 1080p) and duration in seconds (4 | 6 | 8).
REPLICATE_VIDEO_RESOLUTION = os.environ.get("REPLICATE_VIDEO_RESOLUTION", "720p").strip()
REPLICATE_VIDEO_DURATION = int(os.environ.get("REPLICATE_VIDEO_DURATION", "8") or "8")
# Product videos are always portrait; this is intentionally not environment-overridable.
REPLICATE_VIDEO_ASPECT_RATIO = "9:16"
REPLICATE_TTS_MODEL = os.environ.get("REPLICATE_TTS_MODEL", "elevenlabs/v3").strip()
REPLICATE_TTS_VOICE = os.environ.get("REPLICATE_TTS_VOICE", "Rachel").strip()
REPLICATE_TTS_LANGUAGE_CODE = os.environ.get("REPLICATE_TTS_LANGUAGE_CODE", "en").strip()
REPLICATE_FABRIC_MODEL = os.environ.get("REPLICATE_FABRIC_MODEL", "veed/fabric-1.0").strip()
# Fabric 1.0 supports 480p or 720p; default to 480p for faster talking-head generation.
REPLICATE_FABRIC_RESOLUTION = os.environ.get("REPLICATE_FABRIC_RESOLUTION", "480p").strip()
REPLICATE_FFMPEG_MODEL = os.environ.get(
    "REPLICATE_FFMPEG_MODEL",
    "idan054/better-video-merge:6bda9eb61c16dedaa6804792a252cf7a7c260a5c2bf3ac479adab2d3a4e983ad",
).strip()
REPLICATE_ACTOR_MODEL = os.environ.get(
    "REPLICATE_ACTOR_MODEL",
    "bytedance/seedream-5-lite",
).strip()
REPLICATE_ACTOR_IMAGE_COUNT = int(os.environ.get("REPLICATE_ACTOR_IMAGE_COUNT", "4") or "4")
REPLICATE_ACTOR_IMAGE_WIDTH = int(os.environ.get("REPLICATE_ACTOR_IMAGE_WIDTH", "1536") or "1536")
REPLICATE_ACTOR_IMAGE_HEIGHT = int(os.environ.get("REPLICATE_ACTOR_IMAGE_HEIGHT", "2048") or "2048")

JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()

# Optional Replicate LLM model for script/story agent generation.
# If unset or call fails, backend uses deterministic local generation fallback.
REPLICATE_TEXT_MODEL = os.environ.get(
    "REPLICATE_TEXT_MODEL",
    "google/gemini-2.5-flash",
).strip()

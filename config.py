"""Load configuration from environment variables."""
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_BUCKET_PRODUCT_IMAGES = os.environ.get("SUPABASE_BUCKET_PRODUCT_IMAGES", "product-images")

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "").strip()
# Image-to-video model (owner/name or owner/name:version). Default: Google Veo 3.1 Fast
REPLICATE_IMAGE_TO_VIDEO_VERSION = os.environ.get(
    "REPLICATE_IMAGE_TO_VIDEO_VERSION",
    "google/veo-3.1-fast",
).strip()
# Veo defaults: resolution (720p | 1080p), duration in seconds (4 | 6 | 8), aspect_ratio (16:9 | 9:16)
REPLICATE_VIDEO_RESOLUTION = os.environ.get("REPLICATE_VIDEO_RESOLUTION", "720p").strip()
REPLICATE_VIDEO_DURATION = int(os.environ.get("REPLICATE_VIDEO_DURATION", "8") or "8")
REPLICATE_VIDEO_ASPECT_RATIO = os.environ.get("REPLICATE_VIDEO_ASPECT_RATIO", "9:16").strip()

JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()

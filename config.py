"""Load configuration from environment variables."""
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_BUCKET_PRODUCT_IMAGES = os.environ.get("SUPABASE_BUCKET_PRODUCT_IMAGES", "product-images")

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "").strip()
# Image-to-video model (owner/name:version hash)
REPLICATE_IMAGE_TO_VIDEO_VERSION = os.environ.get(
    "REPLICATE_IMAGE_TO_VIDEO_VERSION",
    "aicapcut/stable-video-diffusion-img2vid-xt-optimized:7b595c69ca428904c1907155b93a5580653d1e9dcd407612142595908650dd67",
).strip()
JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()

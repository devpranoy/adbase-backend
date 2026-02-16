# Supabase Storage setup

Do this once in the **Supabase Dashboard** so the app can upload product images and Replicate can read them by URL.

## 1. Create the bucket

1. Open your project at [supabase.com/dashboard](https://supabase.com/dashboard).
2. In the left sidebar go to **Storage**.
3. Click **New bucket**.
4. **Name:** `product-images` (or set env `SUPABASE_BUCKET_PRODUCT_IMAGES` to match).
5. **Public bucket:** turn **ON** so Replicate can fetch the image from the public URL.
6. Click **Create bucket**.

## 2. Policies (optional)

With the **service role** key the backend can read/write regardless of RLS. If you want to lock down the bucket for non–service-role access:

- **Upload:** allow `service_role` (or `authenticated`) to INSERT.
- **Read:** for a public bucket, public read is already allowed.

To add a policy: open the bucket → **Policies** → **New policy** and choose template or custom. For this app, leaving the bucket public and using only the service role key in the backend is enough.

## 3. Create the videos bucket (for persisted outputs)

Completed videos are copied from Replicate into your storage so links don’t expire after 1 hour.

1. In **Storage**, click **New bucket** again.
2. **Name:** `product-videos` (or set env `SUPABASE_BUCKET_VIDEOS` to match).
3. **Public bucket:** turn **ON** so the app can return public video URLs.
4. Click **Create bucket**.

Videos are stored under `completed/<job_id>.mp4`.

## 4. Verify

After the buckets exist and are public, the Flask upload endpoint will store images under `uploads/<filename>` and return the public URL. Replicate will use that URL as the image input. When a job succeeds, the backend downloads the video from Replicate and uploads it to `product-videos`; the database is updated with that permanent URL.

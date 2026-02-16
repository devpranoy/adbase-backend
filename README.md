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

## Environment variables

Set these locally (and in Vercel) for auth, Supabase, and Replicate:

- `SUPABASE_URL` – Supabase project URL  
- `SUPABASE_SERVICE_ROLE_KEY` – Supabase service role key  
- `SUPABASE_BUCKET_PRODUCT_IMAGES` – (optional) Storage bucket name, default `product-images`  
- `REPLICATE_API_TOKEN` – Replicate API token  
- `REPLICATE_IMAGE_TO_VIDEO_VERSION` – (optional) Model version, default aicapcut SVD img2vid  
- `JWT_SECRET` – Secret used to sign login JWTs  

## API

- **POST /api/auth/login** – Body: `{ "username", "password" }`. Returns `{ "token": "..." }`.  
- **POST /api/jobs/upload** – Auth: Bearer token. Form: `image` (file), `prompt` (optional). Returns `job_id`, `image_url`, `status`.  
- **POST /api/jobs/<job_id>/start** – Auth: Bearer. Starts Replicate image-to-video job. Returns `job_id`, `prediction_id`, `status`.  
- **GET /api/jobs/<job_id>** – Auth: Bearer. Returns job status and, when done, `output_video_url`.  
- **GET /api/jobs/<job_id>/result** – Auth: Bearer. Returns `{ "output_video_url": "..." }` when ready, or 202 while processing.  

## One-Click Deploy

Deploy the example using [Vercel](https://vercel.com?utm_source=github&utm_medium=readme&utm_campaign=vercel-examples):

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fvercel%2Fvercel%2Ftree%2Fmain%2Fexamples%2Fflask&demo-title=Flask%20API&demo-description=Use%20Flask%20API%20on%20Vercel%20with%20Serverless%20Functions%20using%20the%20Python%20Runtime.&demo-url=https%3A%2F%2Fvercel-plus-flask.vercel.app%2F&demo-image=https://assets.vercel.com/image/upload/v1669994600/random/python.png)

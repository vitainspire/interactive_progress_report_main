# Backend hosting: AWS Lambda (replacing Render)

## Why

Render's free tier spins the backend down after ~15 min idle, and the next
request then waits ~5 minutes for it to wake up. Parent-facing report links
sent over WhatsApp/SMS were hitting that wait. AWS Lambda has no "sleep" —
worst case is a short cold start on the first request after a quiet period,
not a dead service.

Lambda's free tier (1M requests + ~400,000 GB-seconds/month) is permanent,
not a 12-month trial, unlike EC2.

## What's actually running

- **Region: `ap-southeast-2` (Sydney)** — chosen to match Supabase's pooler
  host (`aws-0-ap-southeast-2.pooler.supabase.com`). Every DB round trip and
  the cold-start migration path depend on this; a mismatched region made
  cold start ~3x slower in testing.
- **ECR repository**: `reprot-card-backend` (typo in the name, cosmetic
  only, left as-is) in account `717827130588`, region `ap-southeast-2`.
- **Lambda function**: `report-card-backend`, container-image based,
  1024 MB memory, 90s timeout.
- **Function URL** (public, Auth type NONE, no CORS config on the Function
  URL itself — FastAPI's own `CORSMiddleware` already handles it, and
  enabling both causes duplicate/conflicting CORS headers):
  `https://2x7wwov5r3nomng7vbqbk5paau0auksx.lambda-url.ap-southeast-2.on.aws/`
- **Frontend**: Vercel's `VITE_API_BASE` env var (Production scope) points
  at `<function url>/api`. Changing it requires an actual redeploy —
  Vite bakes it in at build time, editing the env var alone does nothing
  until the next build.
- **Render**: left running, unused, as an instant rollback — flip
  `VITE_API_BASE` back to the Render URL and redeploy if Lambda ever needs
  to be abandoned. Not yet decommissioned; delete the Render service only
  after Lambda's been solid under real use for a few days.

## Code changes

- `backend/app/lambda_handler.py` — the Lambda entry point:
  ```python
  from mangum import Mangum
  from app.db.database import init_db
  from app.main import app

  init_db()
  handler = Mangum(app, lifespan="off")
  ```
  **`lifespan="off"` is required.** Mangum's default (`"auto"`) re-runs the
  ASGI lifespan — our app's `init_db()` schema migrations *and*
  `close_pool()` — on every single invocation, not just cold start. That
  redid every migration and tore down the DB pool on every request,
  measured at ~30 seconds per call. Calling `init_db()` once here, at
  module import time, means it only runs on an actual cold start (Lambda
  reuses this module, and the connection pool it creates, across warm
  invocations of the same container). `close_pool()` is never called —
  Lambda just freezes/reclaims the execution environment, which is normal.
- `backend/Dockerfile.lambda` — separate from the existing `Dockerfile`
  (which is still used for Render/Koyeb). Based on
  `public.ecr.aws/lambda/python:3.13`, `CMD ["app.lambda_handler.handler"]`.
- `backend/requirements.txt` — added `mangum==0.19.0`.

## Deploying / redeploying

```bash
cd backend
docker build --provenance=false -f Dockerfile.lambda -t reprot-card-backend .
```
`--provenance=false` is required — without it, recent Docker versions
attach an attestation/manifest-list to the image that Lambda's container
import rejects outright ("media type format AWS Lambda does not support").

```bash
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 717827130588.dkr.ecr.ap-southeast-2.amazonaws.com
docker tag reprot-card-backend:latest 717827130588.dkr.ecr.ap-southeast-2.amazonaws.com/reprot-card-backend:latest
docker push 717827130588.dkr.ecr.ap-southeast-2.amazonaws.com/reprot-card-backend:latest
```

Then in the Lambda console: the function's **Image** tab → **Deploy new
image** → pick the `latest` tag again (new digest). No function
recreation needed for routine updates.

## Environment variables (set on the Lambda function, not in code)

Copied from Render's Environment tab — keep both in sync when either
changes:

`DATABASE_URL`, `REPORTCARD_APP_CORS_ORIGINS`, `GOOGLE_API_KEY`,
`REPORTCARD_APP_PUBLIC_BASE_URL` (set to the Function URL above, no
trailing slash — this gets baked into parent WhatsApp/SMS report links),
`REPORTCARD_APP_DEFAULT_COUNTRY_CODE`, `WHATSAPP_CLOUD_API_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE_NAME`,
`WHATSAPP_TEMPLATE_LANG`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_SMS_FROM`, `BHASHINI_USER_ID`, `BHASHINI_ULCA_API_KEY`,
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_DOCUMENT_MODEL`.

Optional — LLM call tracing via LangSmith (see "LangSmith tracing" below):
`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`. Safe to
leave unset entirely; every traced call just runs normally with no
tracing overhead when they're absent.

## LangSmith tracing

Every LLM call this app makes goes through exactly two functions, both
decorated with `@traceable` (`langsmith` package):
`app/integrations/chat.py` (powers both the "Know About Student" chat and
the syllabus-aware study plan) and `app/integrations/syllabus_extraction.py`
(reads an uploaded syllabus/blueprint document). Each call is also tagged
with `account_id` in its trace metadata, so LangSmith's dashboard can be
filtered per school, not just one undifferentiated stream across every
tenant.

To turn tracing on: get an API key at smith.langchain.com, then set
`LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY=<key>`,
`LANGSMITH_PROJECT=report-card-app` (or whatever project name you want
traces grouped under) on the Lambda function. No code change needed to
enable/disable it — `@traceable` is a safe no-op whenever these env vars
are absent, which is also why local dev never needs them set.

## Measured performance (ap-southeast-2, 1024 MB)

- Cold start (first request after an idle gap): ~9.5s.
- Warm request: ~1s.
- Concurrent requests after an idle gap each get their own fresh
  environment in parallel — nobody queues behind anyone else, worst case
  is that same ~9-10s on their first request.

## Known gotchas hit during setup

- AWS CLI access keys must never be pasted into chat/screenshots — if that
  happens, deactivate and recreate the key immediately in IAM → Security
  credentials.
- The ECR console's default "View push commands" build step
  (`docker build -t <repo> .`) builds from the wrong Dockerfile — use
  `-f Dockerfile.lambda` explicitly.
- Changing a Vercel env var does not trigger a rebuild by itself; either
  manually redeploy the latest Production deployment, or push a commit
  (a trivial one, e.g. a frontend version bump, works fine).

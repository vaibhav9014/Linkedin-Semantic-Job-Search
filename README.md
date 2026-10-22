# Semantic Job Match Engine

Upload a resume PDF and receive up to ten relevant, LinkedIn-published job listings with semantic match scores and an explainable skills comparison. Matching uses Sentence-BERT (`all-MiniLM-L6-v2`) and an in-memory FAISS index built for the live results.

The app queries LinkedIn-published results from JSearch through RapidAPI. It does not scrape LinkedIn or call unofficial LinkedIn endpoints. Job listings are normalized, deduplicated, and cached in SQLite.

## How matching works

1. The API extracts text and known skill keywords from the first three pages of the PDF.
2. It derives up to three queries in the form `<role> jobs in <location> via linkedin`.
3. It calls the configured JSearch `/search-v2` URL with `query`, `country`, `date_posted`, `num_pages=1`, and only the mapped `fields`. Results are cached by query and filters in SQLite for 24 hours; subsequent pages can use the response cursor.
4. JSearch results are retained only when `job_publisher` is LinkedIn; HTML is cleaned and duplicate title/company/city listings are removed.
5. The fetched listings are saved to SQLite. The resume and jobs are embedded with Sentence-BERT, then ranked with an in-memory FAISS `IndexFlatIP`.
6. Each result includes its score, skill matches and gaps, application link, source, salary where available, experience level, and posting date.

The UI provides location, experience-level, and date-posted filters over the returned matches.

## Requirements

- Python 3.11
- Node.js 18+
- A RapidAPI key with access to JSearch, configured as `JSEARCH_API_KEY`
- For LinkedIn sign-in: a LinkedIn developer app with **Sign In with LinkedIn using OpenID Connect**
- For posting: the same app must have **Share on LinkedIn** enabled

LinkedIn posting permission is requested separately only when the user chooses to enable sharing. The sign-in flow requests only `openid profile email`; sharing additionally requires `w_member_social`. A post is sent only after the user reviews its preview and clicks **Confirm and post**.

LinkedIn integration follows the current [OpenID Connect sign-in](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2), [OAuth 2.0 authorization-code flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow), and [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api) documentation. The Posts API version is configured as `LINKEDIN_API_VERSION` (default `202610`) and should be advanced with LinkedIn's supported version schedule.

## Local setup

### 1. Configure backend credentials

From the project root:

```bash
cp .env.example backend/.env
```

Edit `backend/.env` and set:

```dotenv
JSEARCH_BASE_URL=https://jsearch.p.rapidapi.com/search-v2
JSEARCH_AUTH_HEADER=x-rapidapi-key
JSEARCH_API_KEY=your_real_rapidapi_key
JSEARCH_COUNTRY=us
JSEARCH_DATE_POSTED=all
JSEARCH_DEFAULT_LOCATION=India
LINKEDIN_CLIENT_ID=your_linkedin_client_id
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret
LINKEDIN_REDIRECT_URI=http://localhost:8000/api/auth/linkedin/callback
APP_SECRET_KEY=your_unique_random_secret
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=["http://localhost:5173"]
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
```

Generate a suitable local signing key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Never put `LINKEDIN_CLIENT_SECRET`, `JSEARCH_API_KEY`, or `APP_SECRET_KEY` in a frontend environment variable. `.env` files are ignored by Git.

In the LinkedIn Developer Portal, add the callback URL above to the app's authorized redirect URLs and enable the OIDC product. To publish posts, also enable Share on LinkedIn. LinkedIn may require app review or product approval before granting these permissions.

### 2. Start the backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

On first startup, Sentence-Transformers downloads its model. The API creates `data/jobs.sqlite3` automatically.

### 3. Start the frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The frontend uses `http://localhost:8000/api` by default; set `VITE_API_BASE_URL` in a frontend environment file if the API is elsewhere.

## API overview

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | API, model, and SQLite status |
| `POST /api/match` | Upload PDF (`file`) and request up to ten matches (`top_k`) |
| `POST /api/embed` | Debug endpoint for embedding text |
| `GET /api/auth/linkedin/login` | Begin LinkedIn OIDC sign-in |
| `GET /api/auth/linkedin/callback` | Validate OAuth state and complete the server-side OIDC flow |
| `GET /api/auth/me` | Return the current member's basic profile |
| `GET /api/auth/linkedin/share-permission` | Request posting permission for a signed-in member |
| `POST /api/linkedin/share` | Publish the user-confirmed post |

OAuth tokens stay in the backend SQLite database. The browser receives only signed, HttpOnly cookies containing a session identifier and short-lived OAuth state; the LinkedIn client secret is never sent to the browser.

## Deploying

`render.yaml` configures the FastAPI service and a persistent disk for SQLite. Add `JSEARCH_API_KEY`, LinkedIn credentials, callback URL, frontend origin, and a randomly generated app secret as Render environment variables. Set `FRONTEND_URL` and `CORS_ORIGINS` to the deployed frontend URL, use `AUTH_COOKIE_SECURE=true` and `AUTH_COOKIE_SAMESITE=none` for separate HTTPS frontend/backend origins, and register the deployed callback URL in LinkedIn Developer Portal.

The repository configures the backend only; deploy the Vite frontend separately and set its `VITE_API_BASE_URL` to the backend's `/api` URL. Do not expose backend secrets in frontend build variables.

## Tests

From `backend/` with dependencies installed:

```bash
pytest tests/ -v -k "not normalized_vector"
```

The targeted tests mock JSearch retry/filtering behavior and LinkedIn's OAuth token, JWKS, and userinfo HTTP calls. The excluded embedding integration test downloads and loads the ML model.

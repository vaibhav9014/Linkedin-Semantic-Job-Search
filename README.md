<div align="center">
Semantic Job Match

Upload a resume. Get ranked, LinkedIn-published job matches with explainable skill gaps.

Independent project. Not affiliated with or endorsed by LinkedIn.

</div>
Table of contents
Demo
Project goal
Problem statement
What it does
Features
How it works
Architecture
Tech stack
Quick start
Environment variables
API documentation
Project structure
Example output
Current status
Milestones
Roadmap
Known limitations
Contributing
License
Connect
Demo


Project goal

Help a job seeker go from a PDF resume to a short, ranked list of relevant, live job listings. Each match shows why it fits and which skills are missing.

Problem statement

Job boards rely on keyword search. A resume that says "built dashboards in Power BI" can miss a posting that asks for "data visualization with BI tools". People then scroll through hundreds of listings, and have no quick way to see which skills they lack for a role. Semantic matching compares meaning, not exact words, and a skill comparison turns each result into a clear next step.

What it does
You upload a PDF resume.
The app builds role queries from your resume and fetches live listings from JSearch (RapidAPI), keeping only those JSearch identifies as published by LinkedIn.
It ranks the listings by semantic similarity to your resume.
For each match it shows matched skills, missing skills, the apply link, source, salary (when available) and posting date.
Optionally, you sign in with LinkedIn and share a selected match after reviewing a preview.

Job data comes from JSearch through RapidAPI, not from LinkedIn's Jobs API. The app does not scrape linkedin.com or use unofficial LinkedIn endpoints.

Features
Semantic ranking: Sentence-BERT (all-MiniLM-L6-v2) embeddings and an in-memory FAISS IndexFlatIP.
Live listings: up to three role/location queries per resume, one page each.
Clean data: HTML stripped from descriptions and duplicates removed by normalized title, company and city.
Skill insights: matched and missing skills for every match.
Filters: by location, experience level and posting date.
Caching: JSearch responses cached in SQLite for 24 hours to protect free-tier quota.
LinkedIn sign-in: OpenID Connect with server-side token exchange and signed, HttpOnly cookies.
Optional sharing: post a match to LinkedIn only after previewing and explicitly confirming.
Privacy by design: resumes are processed in memory and never written to disk or SQLite.
Encrypted OAuth data: tokens and profile JSON are encrypted (Fernet) before storage.
Tests and CI: mocked HTTP tests for the fetcher, search, OAuth and services, run on every push.
How it works
text
Resume PDF → text + skills → role queries → JSearch (LinkedIn-published only)
          → clean + dedupe → SQLite → embeddings → FAISS ranking
          → skill gap per job → ranked results in the UI
The API reads the uploaded PDF and extracts text from at most three pages.
It derives up to three role queries (<role> jobs in <location> via linkedin) from resume titles and skills. The location comes from the resume, or the configured default (India).
It requests one page per query from JSearch with the configured country, date filter and mapped fields.
It keeps LinkedIn-published listings, cleans descriptions and deduplicates.
The listings are saved in SQLite. The resume and listings are embedded and ranked with FAISS.
The API returns up to ten ranked matches. The score measures text similarity. It is not a probability of being hired.
Architecture
PDF upload
Sign in / share
React + Vite UI
FastAPI
PyMuPDF: text + skills
Query builder
JSearch via RapidAPI
Clean + dedupe
SQLite: jobs + cache
Sentence-BERTembeddings
FAISS ranking
Skill gap analysis
LinkedIn OAuth + Posts API
Tech stack
Layer	Technology
Backend	Python 3.11, FastAPI, Pydantic
Resume parsing	PyMuPDF
Embeddings	Sentence-Transformers (all-MiniLM-L6-v2, 384-dim)
Vector search	FAISS (in-memory IndexFlatIP)
Job data	JSearch on RapidAPI
Storage	SQLite
Auth and sharing	LinkedIn OIDC, OAuth 2.0 authorization code flow, Posts API
Frontend	React, Vite, CSS Modules
Testing and CI	pytest, ruff, GitHub Actions
Deployment	Render (backend)
Quick start

Requirements

Python 3.11
Node.js 18+
A RapidAPI key with access to JSearch
(Optional) a LinkedIn developer app with Sign In with LinkedIn using OpenID Connect. For posting, also Share on LinkedIn (w_member_social). LinkedIn may require product approval.
1. Configure the backend
bash
git clone https://github.com/vaibhav9014/Linkedin-Semantic-Job-Search.git
cd Linkedin-Semantic-Job-Search
cp .env.example backend/.env

Generate two independent secrets and paste them into backend/.env:

bash
# APP_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"
# OAUTH_ENCRYPTION_KEY
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

Then set JSEARCH_API_KEY and, for sign-in, the LinkedIn values. See Environment variables.

In the LinkedIn Developer Portal, add http://localhost:8000/api/auth/linkedin/callback as an authorized redirect URL.

2. Start the backend
bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

On first start, Sentence-Transformers downloads the model and the API creates the SQLite database. Check http://localhost:8000/api/health.

3. Start the frontend
bash
cd frontend
npm install
npm run dev

Open http://localhost:5173. The UI calls http://localhost:8000/api by default. Override it with VITE_API_BASE_URL in frontend/.env.

4. Run the tests
bash
cd backend
pytest tests/ -v -k "not normalized_vector"   # fast, no model download
pytest tests/ -v                              # includes the embedding integration test
Environment variables

Copy .env.example to backend/.env. Never commit real values, and never put backend secrets in frontend variables (anything prefixed VITE_ is public).

Variable	Required	Example / default	Purpose
JSEARCH_API_KEY	Yes	your_rapidapi_key	RapidAPI key for JSearch
JSEARCH_BASE_URL	Yes	https://jsearch.p.rapidapi.com/search-v2	JSearch endpoint
JSEARCH_AUTH_HEADER	Yes	x-rapidapi-key	Header name that carries the key
JSEARCH_COUNTRY	Yes	in	Country code for results. Keep it aligned with the default location
JSEARCH_DATE_POSTED	No	all	all, today, 3days, week or month
JSEARCH_DEFAULT_LOCATION	No	India	Used when no location is found in the resume
JSEARCH_CACHE_TTL_SECONDS	No	86400	How long a JSearch response is cached
JSEARCH_MAX_RETRIES	No	2	Retries on 429 and 5xx errors
LINKEDIN_CLIENT_ID	For sign-in	your_linkedin_client_id	LinkedIn app client ID
LINKEDIN_CLIENT_SECRET	For sign-in	your_linkedin_client_secret	LinkedIn app secret (server only)
LINKEDIN_REDIRECT_URI	For sign-in	http://localhost:8000/api/auth/linkedin/callback	Must match the Developer Portal exactly
LINKEDIN_API_VERSION	For sharing	202610	Posts API version; update before it sunsets
APP_SECRET_KEY	Yes	(generated)	Signs session and state cookies
OAUTH_ENCRYPTION_KEY	Yes	(generated)	Fernet key that encrypts stored OAuth data
FRONTEND_URL	Yes	http://localhost:5173	Where to redirect after sign-in
CORS_ORIGINS	Yes	["http://localhost:5173"]	Allowed frontend origins (JSON list)
AUTH_COOKIE_SECURE	No	false locally, true in production	HTTPS-only cookies
AUTH_COOKIE_SAMESITE	No	lax	Cookie SameSite policy
JOBS_DB_PATH	No	data/jobs.sqlite3	SQLite location (/data/jobs.sqlite3 on Render)

Keep OAUTH_ENCRYPTION_KEY safe and backed up separately from the database. If it is lost or changed, stored OAuth data becomes unreadable and users must sign in again.

API documentation

Base URL: http://localhost:8000/api. Interactive docs are at http://localhost:8000/docs.

Method	Endpoint	Purpose
GET	/health	API, model and job-store status
POST	/match	Upload a PDF (file) and get ranked matches (top_k, 1–10)
POST	/embed	Debug: embed a text string
GET	/auth/linkedin/login	Begin LinkedIn OIDC sign-in
GET	/auth/linkedin/callback	Validate OAuth state and finish sign-in
GET	/auth/me	Basic profile of the signed-in member
GET	/auth/linkedin/share-permission	Request posting permission
POST	/linkedin/share	Publish the post the user previewed and confirmed

Example request

bash
curl -X POST http://localhost:8000/api/match \
  -F "file=@resume.pdf" \
  -F "top_k=10"

Share request body (POST /linkedin/share)

json
{
  "title": "Data Analyst",
  "company": "Example Corp",
  "apply_url": "https://example.com/jobs/123",
  "source": "LinkedIn",
  "commentary": "Text the user reviewed in the preview"
}

The browser receives only signed, HttpOnly session cookies. It never receives the LinkedIn client secret or an access token.

Project structure
text
.
├── .github/workflows/test.yml     # CI: pytest + ruff
├── backend/
│   ├── api/
│   │   ├── main.py                # app startup, model + store loading
│   │   ├── routes.py              # /health, /match, /embed
│   │   └── auth_routes.py         # LinkedIn sign-in and sharing
│   ├── core/config.py             # settings from environment
│   ├── models/schemas.py          # Pydantic request/response models
│   ├── services/
│   │   ├── pdf_service.py         # PDF text extraction + skills
│   │   ├── job_fetcher.py         # JSearch client, filtering, cleaning
│   │   ├── job_store.py           # SQLite jobs + response cache
│   │   ├── embedding_service.py   # Sentence-BERT
│   │   ├── search_service.py      # FAISS ranking
│   │   ├── gap_service.py         # matched vs missing skills
│   │   └── linkedin_auth.py       # OIDC + Posts API
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/            # UploadZone, JobCard, ScoreBar, SkillTags, ...
│   │   └── utils/api.js
│   └── .env.example
├── docs/screenshots/              # demo images (add yours here)
├── .env.example
├── render.yaml
├── LICENSE
└── README.md
Example output

Abridged response from POST /api/match. The values are illustrative.

json
{
  "resume_text_preview": "Data analyst with experience in SQL, Power BI and Python...",
  "resume_skills": ["sql", "power bi", "python", "excel"],
  "search_queries": [
    "data analyst jobs in India via linkedin",
    "power bi developer jobs in India via linkedin"
  ],
  "total_jobs_searched": 27,
  "matches": [
    {
      "job_id": "abc123",
      "title": "Power BI Developer",
      "company": "Example Corp",
      "location": "Gurugram, Haryana, India",
      "score": 0.71,
      "matched_skills": ["power bi", "sql", "excel"],
      "missing_skills": ["dax", "azure"],
      "apply_url": "https://example.com/jobs/123",
      "source": "LinkedIn",
      "experience_level": "mid",
      "posted_at": "2026-10-18T09:30:00Z"
    }
  ]
}
Current status

Working today

Resume upload and PDF text extraction
Live LinkedIn-published listings through JSearch, with cleaning, dedupe and a 24-hour cache
Semantic ranking with Sentence-BERT and FAISS
Matched and missing skills per job
Location, experience-level and date filters in the UI
LinkedIn sign-in (OIDC) with encrypted token storage
User-confirmed sharing to LinkedIn
Automated tests and CI
Render deployment configuration

Not done yet: a public live demo, scheduled job refresh, and the roadmap items below.

Milestones
 M1: FastAPI backend, PDF parsing, SBERT embeddings, FAISS search
 M2: React frontend with upload, scanning state and result cards
 M3: Live job fetching from JSearch (LinkedIn-published only) with SQLite cache
 M4: Skill gap analysis, filters, apply links and job metadata
 M5: LinkedIn sign-in and confirm-before-post sharing
 M6: Encrypted OAuth storage, tests and CI
 M7: Public deployment with screenshots and demo
 M8: Shortlist-likelihood estimate and AI-assisted resume profile
 M9: Recruiter connect section
 M10: Scheduled refresh and Docker packaging
Roadmap
Better resume understanding: use an LLM to extract a structured profile (target roles, seniority, skills) and generate smarter search queries.
Shortlist-likelihood estimate: a transparent, clearly labelled blend of semantic similarity, skill coverage, experience fit and location, shown with its breakdown. It would be an estimate, not a hiring probability.
Connect section: apply links, recruiter details when a source provides them, user-opened people-search links, and AI-drafted outreach messages. No scraping of personal contact data.
More sources: Adzuna, and public company job-board APIs such as Greenhouse and Lever.
Scheduled refresh of cached listings, and automatic expiry of old rows.
Docker packaging and a documented one-click deploy.
Evaluation: a small hand-labelled set to measure ranking quality (for example precision@k).
Score calibration so similarity scores read more naturally.
Known limitations
Coverage depends on JSearch. Results are what JSearch retrieves, including what Google for Jobs has indexed from LinkedIn. Listings can be missing, delayed, duplicated upstream or no longer active.
Free-tier quota is small. The cache helps, but new queries still use quota.
No Jobs API access. The app does not use LinkedIn's Jobs API. LinkedIn credentials are used only for sign-in and sharing.
Keyword-based skills. Skill detection uses a keyword list, not a deeper resume-understanding model.
Similarity is not suitability. A score is a ranking signal. It is not a probability of being hired or a guarantee of qualification.
Filters apply to returned matches (at most ten), not to the whole job market.
Location detection is a text pattern. If the resume has no clear location, the default is used.
Listings have no automatic expiry in SQLite, and session rows remain until cleaned up.
LinkedIn product approval may be required for sign-in and posting, depending on your developer app.
Cross-site cookies: separate frontend and backend domains can break sign-in in browsers that block third-party cookies. Prefer a same-site deployment or a same-origin proxy.

Data and privacy

Resume bytes and extracted text stay in request memory and are not saved.
Resume-derived role queries and the location are sent to JSearch. The resume itself is not.
JSearch responses are cached for 24 hours. Normalized listings persist in SQLite.
OAuth tokens and profile JSON are encrypted before storage. Protect the database backups and the encryption key separately.
Deploying to Render

render.yaml defines a paid 1c-2g web service and a 1 GB persistent disk mounted at /data. Persistent disks need a paid service, and 2 GB of memory is a practical starting point for PyTorch plus Sentence-Transformers. Monitor memory during model load. Plans and pricing change, so check Render's compute plans.

Set these in the Render dashboard: JSEARCH_API_KEY, LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_REDIRECT_URI, APP_SECRET_KEY, OAUTH_ENCRYPTION_KEY, FRONTEND_URL, CORS_ORIGINS. Use AUTH_COOKIE_SECURE=true, and register the deployed callback URL in the LinkedIn Developer Portal. Deploy the Vite frontend separately and set its VITE_API_BASE_URL to the backend's /api URL.

The Posts API version is 202610. LinkedIn's versioning docs say versioned releases are supported for at least one year. Check the schedule and update LINKEDIN_API_VERSION before it sunsets. The Posts API docs list the current endpoint and headers.

Contributing

Contributions are welcome.

Fork the repository and create a branch: git checkout -b feature/your-change
Make your change and add or update tests.
Run pytest tests/ -v -k "not normalized_vector" and ruff check backend/ from the repository root.
Open a pull request that explains what changed and why.

For larger changes, please open an issue first. Never commit .env files, API keys or the SQLite database.

License

Released under the MIT License.

Connect

Built by Vaibhav.

GitHub: @vaibhav9014
Found a bug or have an idea? Open an issue.
LinkedIn: 'https://www.linkedin.com/in/vaibhav-singh-69681a228/?isSelfProfile=true'
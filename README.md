# Interview Intelligence Platform

An AI-powered interview preparation and candidate evaluation platform.
Upload a resume (PDF or DOCX) and a job description, get a skill-match
score, generate personalized interview questions, answer them by voice or
text, and get AI-scored feedback — with PostgreSQL persistence throughout.

## Run the full app

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # add GLM_API_KEY at minimum
streamlit run app.py
```

Opens at `http://localhost:8501`. **`DATABASE_URL` is required to sign
in** — accounts have to live somewhere, so this is the one place that isn't
best-effort. Everything else (`GOOGLE_SPEECH_API_KEY`, and DB writes for
resumes/JDs/questions/answers/reports once you're logged in) stays optional
and degrades gracefully. The sidebar shows a live "Database connected" /
"Database not configured" indicator.

Flow: Home → pick Student or Recruiter → **Continue with Google** (scoped to
that role) → land straight on that dashboard. A Profile page (name, email,
phone, account type, Log Out) is available from the sidebar once logged in.
Sign-in is Google-only — there's no email/password/signup form.

To set up PostgreSQL:

```bash
# after adding DATABASE_URL to .env
python -m database.init_db
```

### Google Sign-In setup

Sign-in uses Streamlit's native OIDC support (`st.login()`/`st.user`), not a
custom auth backend. To enable it:

1. In [Google Cloud Console](https://console.cloud.google.com/) → **APIs &
   Services → Credentials**, create an **OAuth client ID** of type
   **Web application**, with an authorized redirect URI of
   `http://localhost:8501/oauth2callback` (add your production URL's
   `/oauth2callback` too before deploying).
2. Create `.streamlit/secrets.toml` (already gitignored — never commit it)
   with the client ID/secret pasted into **two** provider blocks sharing the
   same real Google client:

   ```toml
   [auth]
   redirect_uri = "http://localhost:8501/oauth2callback"
   cookie_secret = "<random — e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`>"

   [auth.student]
   client_id = "<GOOGLE_CLIENT_ID>.apps.googleusercontent.com"
   client_secret = "<GOOGLE_CLIENT_SECRET>"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

   [auth.recruiter]
   client_id = "<SAME_GOOGLE_CLIENT_ID>.apps.googleusercontent.com"
   client_secret = "<SAME_GOOGLE_CLIENT_SECRET>"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```

   Two provider names sharing one real client is what lets the app recover
   which portal (student/recruiter) the user picked before authenticating —
   `st.session_state` doesn't survive the Google redirect round-trip, but
   the provider name does, via `st.user["provider"]`.

Without this file, the app shows a friendly "Google sign-in isn't configured
yet" message instead of a button — nothing crashes.

The standalone REST API (`api/`, `python main.py`) is also still available
for other integrations — see "Running the API" below.

## Modules

1. **Resume Processing** — PDF or DOCX → structured resume JSON
2. **JD Parsing** — raw JD text → structured JD JSON
3. **Matching Engine** — resume JSON + JD JSON → weighted skill match score
4. **Question Generation** — resume + JD + match result → personalized questions
5. **Answer Evaluation** — interview question + candidate answer → scored feedback
6. **Speech-to-Text** — recorded voice answer → transcribed text
7. **Database** — PostgreSQL persistence for every stage above
8. **API** — FastAPI routes wiring the first five modules together
9. **App** (`app.py`) — the Streamlit frontend, wired to every module above
   directly (in-process) plus the database layer

`app.py` is the full end-to-end application. `api/` is a second,
independent REST entry point over the same shared business-logic modules
(useful for other frontends/integrations) — both call the same underlying
packages, so there's no duplicated logic.

## Pipeline

```text
Resume PDF ────────► Resume Processing ────► Parsed Resume JSON ──┐
                                                                    │
Raw JD Text ───────► JD Parsing ────────────► Parsed JD JSON ─────┼──► Matching Engine ──► Match Result JSON
                                                                    │              │
                                                                    │              ▼
                                                                    └──► Question Generation ──► Generated Questions

Interview Question + Candidate Answer ──► Answer Evaluation ──► Evaluation Result
```

## Running the API

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then fill in GLM_API_KEY
python main.py
```

The API is now live at `http://127.0.0.1:8000`:

- **Swagger UI**: `http://127.0.0.1:8000/docs` — interactive, try every
  endpoint directly in the browser.
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **Health check**: `GET /api/v1/health`

## API Endpoints

| Method | Path                        | Description                                          |
|--------|-----------------------------|-------------------------------------------------------|
| POST   | `/api/v1/resume/parse`      | Upload a resume PDF → structured resume JSON          |
| POST   | `/api/v1/jd/parse`          | `{"jd_text": "..."}` → structured JD JSON              |
| POST   | `/api/v1/match`             | `{"resume_json": {...}, "jd_json": {...}}` → match score |
| POST   | `/api/v1/questions/generate`| resume + JD + match JSON → generated interview questions |
| POST   | `/api/v1/interview/evaluate`| question + candidate answer → scored evaluation        |
| POST   | `/api/v1/pipeline/analyze`  | resume file + JD text → resume + JD + match in one call |
| GET    | `/api/v1/health`            | Liveness check                                         |

All error responses share one shape: `{"error_type": "...", "detail": "..."}`.
Bad input / unparseable LLM output → `422`. Unexpected server errors → `500`.

### Example: end-to-end curl walkthrough

```bash
# 1. Parse a JD
curl -X POST http://127.0.0.1:8000/api/v1/jd/parse \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "We are hiring a Backend Engineer with Python, SQL, and Docker experience. Bachelor'"'"'s degree required."}'

# 2. Parse a resume
curl -X POST http://127.0.0.1:8000/api/v1/resume/parse \
  -F "file=@samples/resume_sample.pdf"

# 3. Match them (paste the JSON from steps 1 & 2)
curl -X POST http://127.0.0.1:8000/api/v1/match \
  -H "Content-Type: application/json" \
  -d '{"resume_json": {...}, "jd_json": {...}}'

# 4. Generate questions
curl -X POST http://127.0.0.1:8000/api/v1/questions/generate \
  -H "Content-Type: application/json" \
  -d '{"resume_json": {...}, "jd_json": {...}, "match_result_json": {...}, "difficulty": "medium", "question_count": 5}'

# 5. Evaluate a candidate's spoken/written answer
curl -X POST http://127.0.0.1:8000/api/v1/interview/evaluate \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain REST vs GraphQL", "candidate_answer": "...", "job_role": "Backend Engineer", "required_skills": ["Python", "SQL"]}'
```

Or skip straight to `/docs` and use the Swagger "Try it out" buttons — no
curl required.

## Public Python APIs (for direct import, without the API layer)

```python
from resume_processing import process_resume
from jd_parsing import parse_jd
from matching_engine import run_matching
from question_generation import generate_questions
from answer_evaluation import evaluate_answer

resume_json = process_resume("path/to/resume.pdf").model_dump()
jd_json = parse_jd(raw_jd_text).model_dump()
match_result = run_matching(resume_json, jd_json)
questions = generate_questions(
    resume_json=resume_json,
    jd_json=jd_json,
    match_result_json=match_result.to_dict(),
    difficulty="medium",
    question_count=5,
)
evaluation = evaluate_answer(
    question=questions.questions[0].question,
    candidate_answer="...",
    job_role=jd_json["role"],
    required_skills=jd_json["required_skills"],
)
```

## Project Structure

```text
.
├── README.md
├── requirements.txt
├── .env.example
├── main.py                        # python main.py → runs the API
├── api/                           # FastAPI layer (routes, schemas, error handling)
│   ├── main.py                    # FastAPI app: uvicorn api.main:app
│   ├── schemas.py                 # request/response models
│   ├── exception_handlers.py      # maps every module's exceptions → HTTP responses
│   ├── routes/
│   │   ├── resume.py
│   │   ├── jd.py
│   │   ├── matching.py
│   │   ├── questions.py
│   │   ├── evaluation.py
│   │   └── pipeline.py            # combined resume+JD+match convenience route
│   └── tests/
├── resume_processing/             # PDF → structured resume JSON
│   ├── __init__.py / config.py / exceptions.py / schema.py
│   ├── pdf_extractor.py / text_cleaner.py / resume_parser.py
│   ├── validator.py / normalizer.py / process_resume.py
│   ├── prompts/resume_parser_prompt.txt
│   └── tests/
├── jd_parsing/                    # raw JD text → structured JD JSON
│   ├── __init__.py / config.py / exceptions.py / schema.py
│   ├── jd_parser.py / output_validator.py / parse_jd.py
│   ├── prompts/jd_parser_prompt.txt
│   └── tests/
├── matching_engine/                # resume JSON + JD JSON → weighted match score
│   ├── __init__.py / exceptions.py / matching_engine.py
│   └── tests/
├── question_generation/           # resume + JD + match → personalized questions
│   ├── __init__.py / config.py / exceptions.py / schema.py
│   ├── prompt_builder.py / output_validator.py / generate_questions.py
│   ├── prompts/question_generation_prompt.txt
│   └── tests/
├── answer_evaluation/             # question + candidate answer → scored feedback
│   ├── __init__.py / config.py / exceptions.py / schema.py
│   ├── evaluator.py / output_validator.py / evaluate_answer.py
│   ├── prompts/evaluation_prompt.txt
│   └── tests/
├── samples/
└── scripts/
    ├── demo_parser.py             # resume parser demo (requires GLM_API_KEY)
    └── demo_matching.py           # matching engine demo (no API key needed)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env
```

Add your GLM credentials to `.env` — **one set of credentials, shared by
every LLM-backed module** (resume parsing, JD parsing, question generation,
answer evaluation):

```text
GLM_API_KEY=your_api_key_here
GLM_MODEL=glm-4.5-flash
GLM_API_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
```

## Running Tests

The project uses `pytest` with markers for the different test layers:

- **Unit/API tests**: fast local tests for business logic, validation, and FastAPI routes.
- **E2E tests**: mocked cross-module API flows and Streamlit UI flows.
- **Integration tests**: real PostgreSQL repository tests, skipped unless `TEST_DATABASE_URL` is set.

Run the normal local suite:

```bash
.venv/bin/python -m pytest
```

Run only the fast non-database tests:

```bash
.venv/bin/python -m pytest -m "not integration"
```

Run only backend/UI end-to-end tests:

```bash
.venv/bin/python -m pytest -m e2e
```

Run PostgreSQL integration tests:

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/interview_platform_test \
  .venv/bin/python -m pytest -m integration
```

Run coverage locally:

```bash
.venv/bin/python -m pytest -m "not integration" --cov=. --cov-report=term-missing
```

Most LLM-backed behavior is tested without network access by mocking the raw
HTTP boundary. The matching engine is deterministic and tested directly. The
Streamlit tests use `streamlit.testing.v1.AppTest` to verify navigation,
dashboard rendering, warnings, interview submission, and report rendering.

The repository also includes a GitHub Actions workflow in
`.github/workflows/test.yml` that runs non-integration tests with coverage and
then runs integration tests against a temporary PostgreSQL service.

## Module Contracts

### `ParsedResume`

```json
{
  "name": "", "email": "", "phone": "", "linkedin": "", "github": "",
  "skills": [], "education": [], "experience": [], "projects": [], "certifications": []
}
```

### `ParsedJD`

```json
{
  "role": "", "required_skills": [], "preferred_skills": [],
  "responsibilities": [], "experience_level": "", "education_requirement": ""
}
```

### `MatchResult`

```json
{
  "score": 0.0, "required_coverage": 0.0, "preferred_coverage": 0.0,
  "matched_required": [], "missing_required": [],
  "matched_preferred": [], "missing_preferred": [],
  "inferred_skills": [], "skill_gap": [{"skill": "", "type": "", "priority": ""}]
}
```

### `GeneratedQuestions`

```json
{"questions": [{"question": "", "category": "", "difficulty": "", "reason": ""}]}
```

### `EvaluationResult`

```json
{
  "overall_score": 0, "correctness": 0, "keyword_coverage": 0, "clarity": 0,
  "communication": 0, "completeness": 0, "strengths": [], "improvements": [],
  "feedback": "", "ideal_answer": ""
}
```

## What changed when this was wired into a backend

Starting from the four standalone module drafts, the following were fixed
so the pipeline is *actually* connected end to end, not just individually
functional:

- **Unified LLM client config.** The JD parser and answer evaluator drafts
  used a separate OpenAI-SDK client keyed off `GLM_BASE_URL`/`MODEL`, while
  the rest of the project reads `GLM_API_KEY`/`GLM_MODEL`/`GLM_API_URL` via
  raw `httpx` calls. Both new modules now follow the existing convention —
  one `.env`, one client pattern, no silently-unset variables.
- **Prompt file paths made CWD-independent.** The drafts loaded prompts via
  a relative path (`"prompts/jd_prompt.txt"`), which only works if the
  process happens to be launched from exactly the right directory. Every
  module now resolves its prompt via `Path(__file__).parent`, matching
  `resume_processing`/`question_generation`.
- **`education_requirement` field added to `ParsedJD`.** The matching engine
  reads `jd_json["education_requirement"]` for degree-level scoring, but
  that field didn't exist in the JD parser's schema — it was silently always
  empty, so every JD looked like it had no education requirement. Added to
  both the schema and the prompt.
- **Dropped the stray `required_skill_relevance` field** from the evaluation
  schema — the evaluation prompt never asks the model to produce it and it
  isn't part of the `overall_score` formula, so keeping it would only ever
  return a misleading `0`.
- **Call vs. validate-with-retry separated.** The drafts mixed the GLM call
  and the retry loop into one function. Each module now has a single-call
  function (`jd_parser.py`, `evaluator.py`) and a separate
  `output_validator.py` that owns retry logic — matching the pattern
  already used by `question_generation`, and making both pieces unit-
  testable without mocking HTTP.
- **Defensive input validation added to the matching engine** (raises
  `MatchingEngineError` on non-dict input) since it's now reachable directly
  from an untrusted API request body, not just from trusted internal code.

## Integration Notes

- Teammates should use only the public imports from each module's
  `__init__.py` (see "Public Python APIs" above) — internals (`jd_parser`,
  `evaluator`, `output_validator`, etc.) are not part of the contract.
- Convert Pydantic objects to dictionaries with `.model_dump()` (or
  `MatchResult.to_dict()`) before passing data to another module, storing
  it, or returning it from an API route.
- No frontend, database, or session storage is implemented here by design —
  this repo is backend-only. A frontend (Streamlit, React, etc.) can be
  pointed at these REST endpoints without any backend code changes, and
  `ALLOWED_ORIGINS` in `.env` controls which origins CORS will accept.
- The repository expects Python 3.11+.
- Local files such as `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, and
  `.DS_Store` should not be committed.

## Demos

```bash
# Resume parser demo — requires GLM_API_KEY in .env
python scripts/demo_parser.py samples/resume_sample.txt

# Matching engine demo — no API key needed, pure logic
python scripts/demo_matching.py
```

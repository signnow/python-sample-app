# SignNow Python Sample App

[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-cyan)](https://fastapi.tiangolo.com/)
[![SignNow SDK](https://img.shields.io/badge/SignNow_SDK-3.0+-light)](https://pypi.org/project/signnow-python-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

A FastAPI application demonstrating the SignNow API via the official [`signnow-python-sdk`](https://pypi.org/project/signnow-python-sdk/) package from PyPI.

## Quick Start

### 1. Enter the directory

```bash
cd SampleApps/python-sample-app
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your SignNow credentials:

| Variable | Example | Description |
|---|---|---|
| `SIGNNOW_API_HOST` | `https://api.signnow.com` | Production or sandbox URL |
| `SIGNNOW_API_BASIC_TOKEN` | `c2lnbk5vdy4...` | Base64 token from [API Dashboard](https://app.signnow.com/webapp/api-dashboard/keys) |
| `SIGNNOW_API_USERNAME` | `you@example.com` | Your SignNow account email |
| `SIGNNOW_API_PASSWORD` | `••••••` | Your SignNow account password |
| `SIGNNOW_DOWNLOADS_DIR` | `/tmp/signnow-downloads` | Where downloaded documents are cached |
| `SN_SIGNER_EMAIL` | `signer@example.com` | Default embedded signer email |

### 3. Run with Docker Compose (recommended)

```bash
docker compose up --build
```

App is available at `http://localhost:8080`. Stop with `Ctrl+C`; remove with `docker compose down`.

### 4. Run with Docker (without Compose)

```bash
docker build -t python-sample-app .
docker run --env-file .env -p 8080:8080 python-sample-app
```

### 5. Run locally (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 6. Open a sample

```
http://localhost:8080/samples/EmbeddedSignerConsentForm
```

`http://localhost:8080/samples` lists all available samples.

## Available Samples (20)

| Sample | Description |
|---|---|
| EmbeddedSignerConsentForm | Consent form with single embedded signer |
| EmbeddedSenderWithoutFormFile | Sales proposal — embedded sender |
| EmbeddedSenderWithFormCreditLoanAgreement | Credit loan agreement |
| EmbeddedSignerConsumerServices | Veterinary intake form |
| EmbeddedSignerPatientIntakeForm | Patient intake (healthcare) |
| EmbeddedSignerWithFormInsurance | Insurance claim form |
| MedicalInsuranceClaimForm | Medical insurance claim |
| EmbeddedEditingAndSigningDG | Document generation: edit + sign |
| EmbeddedSenderWithFormAndFirstSigner | Sender is also first signer |
| EmbeddedSenderWithFormDG | Document generation variant |
| EmbeddedSenderWithFormDGAdjunct | DG adjunct form |
| EmbeddedSenderWithFormDGConstr | DG construction form |
| ISVWithFormAndOneClickSendBasicPrefill | ISV one-click send, basic prefill |
| ISVWithFormAndOneClickSendMergeFields | ISV one-click send, merge fields |
| HROnboardingSystem | HR onboarding multi-document flow |
| UploadEmbeddedSender | Upload PDF + embedded sender |
| PrefillAndEmbeddedSendingAgreement | Prefill + embedded send |
| PrefillAndOneClickSendingAgreement | Prefill + one-click send |
| EVDemoSendingAnd3EmbeddedSigners | Real estate: 3 sequential embedded signers |
| UploadEmbeddedEditingAndInvite | Upload PDF, embedded edit, invite |

## Project Structure

```
app/
  main.py               FastAPI app, static mounts
  routing.py            /samples/{name} and /api/samples/{name} dispatch
  sample_interface.py   SampleController ABC
  settings.py           .env loader (pydantic-settings)
samples/
  <SampleName>/
    __init__.py
    index_controller.py IndexController(SampleController)
    index.html          UI served on GET /samples/<SampleName>
static/                 Shared CSS, JS, images, error.html
tests/                  Smoke tests (42 tests)
```

## Routing

| Method | Path | Handler |
|---|---|---|
| GET | `/` | 404 error page |
| GET | `/samples/{name}` | `samples.<name>.IndexController.handle_get` |
| POST | `/api/samples/{name}` | `samples.<name>.IndexController.handle_post` |
| GET | `/css/*`, `/js/*`, `/img/*`, etc. | Shared static files |

Sample names must match `^[a-zA-Z0-9_]+$`. Any folder under `samples/` whose `index_controller.py` exports an `IndexController` subclass of `SampleController` is automatically reachable — no registration needed.

## Add a New Sample

1. `mkdir samples/MyNewSample && touch samples/MyNewSample/__init__.py`
2. Create `samples/MyNewSample/index_controller.py`:
   ```python
   from app.sample_interface import SampleController
   from fastapi.responses import HTMLResponse
   from pathlib import Path

   class IndexController(SampleController):
       def handle_get(self, query_params):
           return HTMLResponse((Path(__file__).parent / "index.html").read_text())

       def handle_post(self, form_data):
           ...
   ```
3. Create `samples/MyNewSample/index.html`.
4. Add `"MyNewSample"` to the `SAMPLES` list in `tests/test_routes_samples.py`.
5. `pytest tests/` — confirms the controller loads.

No JSON whitelist, no registration file — the routing layer discovers samples at request time.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

42 smoke-level tests:
- 2 settings defaults / overrides
- 3 SampleController ABC contract
- 11 name-validation + dispatch (regex, load_controller, 404, static mounts)
- 6 HTTP layer (root, unknown, invalid name, static CSS/img)
- 20 per-sample module loads (one per sample)

Tests confirm the app starts and each sample's controller loads correctly.
They do **not** exercise real SignNow API calls (live credentials required).

## SDK Notes

Known quirks in `signnow-python-sdk` 3.0 that are worth knowing before you dig into controllers:

**Multipart upload** — `DocumentPostRequest` accepts a file path string, not a file object. Pass the absolute path; the SDK opens the file internally.

**`handle_post` receives `Request`** — FastAPI passes the full `Request` object (not pre-parsed JSON). Call `await request.json()` or `await request.form()` depending on the content type.

**Embedded invite response** — `DocumentInvitePostResponse.data` is a list; each item exposes `.role_id` and `.id` (the invite ID needed for `DocumentInviteLinkPost`).

## Tech Stack

- Python 3.12 (tested on 3.13)
- FastAPI 0.115 + Uvicorn 0.32
- `signnow-python-sdk` 3.0.0 (from PyPI)
- `pydantic-settings` 2.5 for `.env` loading
- pytest (tests)
- Docker: single-stage `python:3.12-slim`

## GitHub Copilot Extension

Get AI-powered SignNow code suggestions in your IDE:
[github.com/apps/signnow](https://github.com/apps/signnow) — start prompts with `@signnow`.

## License

See [LICENSE](./LICENSE).

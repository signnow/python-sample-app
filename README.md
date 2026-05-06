# SignNow Python Sample App

A FastAPI application demonstrating the SignNow API via the official `signnow-python-sdk` package from PyPI. 

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

| Variable | Description |
|---|---|
| `SIGNNOW_API_HOST` | `https://api.signnow.com` (production) or sandbox URL |
| `SIGNNOW_API_BASIC_TOKEN` | Base64 token from your SignNow API dashboard |
| `SIGNNOW_API_USERNAME` | Your SignNow account email |
| `SIGNNOW_API_PASSWORD` | Your SignNow account password |
| `SIGNNOW_DOWNLOADS_DIR` | Where downloaded documents are cached (default `/tmp/signnow-downloads`) |
| `SN_SIGNER_EMAIL` | Default embedded signer email |

### 3. Run with Docker Compose (recommended)

```bash
docker compose up --build
```

This builds the image, starts the container with `.env` mounted, and exposes the app on `http://localhost:8080`. Stop with `Ctrl+C`; remove with `docker compose down`.

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

Navigate to `http://localhost:8080/samples/<SampleName>`, e.g.:

```
http://localhost:8080/samples/EmbeddedSignerConsentForm
```

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
| PrefillAndEmbeddedSendingAgreement | Prefill + embedded send (Java-only origin) |
| PrefillAndOneClickSendingAgreement | Prefill + one-click send (Java-only origin) |
| EVDemoSendingAnd3EmbeddedSigners | Real estate: 3 sequential embedded signers (PHP-only origin) |
| UploadEmbeddedEditingAndInvite | Upload PDF, embedded edit, invite (PHP-only origin) |

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
    index.html          Thank-you / download UI
static/                 Shared CSS, JS, images, error.html
tests/                  Smoke tests (42 tests)
```

## Routing

| Method | Path | Handler |
|---|---|---|
| GET | `/` | 404 error page |
| GET | `/samples/{name}` | Dispatch to `samples.<name>.IndexController.handle_get` |
| POST | `/api/samples/{name}` | Dispatch to `samples.<name>.IndexController.handle_post` |
| GET | `/css/*`, `/js/*`, `/img/*`, `/fonts/*`, `/assets/*` | Shared static files |

Sample discovery is by convention: any folder under `samples/` matching the regex `^[a-zA-Z0-9_]+$` whose `index_controller.py` exports an `IndexController` subclass of `SampleController` is automatically reachable.

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
- 2 settings defaults/overrides
- 3 SampleController ABC contract
- 11 name-validation + dispatch (regex, load_controller, 404 responses, static mounts)
- 6 HTTP-layer (root, unknown, invalid name, static CSS/img)
- 20 per-sample module-loads (one per sample)

Tests are smoke-level only: they confirm the FastAPI app starts, dispatch routes to each sample's controller, and 404 pages render correctly. They do NOT exercise real SignNow API calls (those require live credentials).

## Tech Stack

- Python 3.12 (tested on 3.14)
- FastAPI 0.115 + Uvicorn 0.32
- `signnow-python-sdk` 3.0.0 (from PyPI)
- `pydantic-settings` 2.5 for `.env` loading
- Docker: single-stage `python:3.12-slim`

## License

See repository root.

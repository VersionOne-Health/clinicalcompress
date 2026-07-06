# clinicalcompress demo UI

This is a demonstration front end for the `clinicalcompress` library —
it is **not** a production service. It's a stateless FastAPI app that
calls the real library so the demo shows genuine behavior, side-by-side
against a deliberately unsafe naive baseline used only to illustrate the
contrast.

The same page is intended to live at
https://versionone.health/tools/clinicalcompress.

## Run locally

```bash
pip install -e ".[ui]"
uvicorn webui.app:app --reload --port 8000
```

Then open http://localhost:8000.

No database, no accounts, no sessions, and no browser storage are used —
all state lives in the page for the duration of your visit.

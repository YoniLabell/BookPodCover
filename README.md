# BookPod Checker (FastAPI)

בדיקת PDF לתוכן וכריכה לפי מידות טרים/בליד וחישוב שדרה.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# open http://127.0.0.1:8000/
```

## Deploy to Render (no Docker)
- Repo must include: `requirements.txt`, `main.py`, `templates/`, `static/`, `gunicorn_conf.py`, `render.yaml`, `runtime.txt`
- Render build command: `pip install -r requirements.txt`
- Start command: `gunicorn -k uvicorn.workers.UvicornWorker -c gunicorn_conf.py main:app`
- Health check: `/`

## Deploy with Docker (optional)
- Keep `Dockerfile` in repo and create a **Docker** web service on Render.
```dockerfile
# see Dockerfile in repo
```

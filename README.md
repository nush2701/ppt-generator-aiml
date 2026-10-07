# AI PowerPoint Generator

An early-stage project for a web application that will generate PowerPoint presentations from natural-language requests. This repository currently contains only the initial backend and frontend scaffolding; presentation generation is not implemented.

## Technology stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Backend: Python, FastAPI, Uvicorn

## Development status

Project initialization is complete. The backend health endpoint and frontend landing page are available; all generation features remain future work.

## Run locally

Backend (from the repository root):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The health endpoint is at http://127.0.0.1:8000/health.

Frontend (in a second terminal, from the repository root):

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 in a browser.

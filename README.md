# TenderIQ — VS Code-ready project

This folder is a clean, portable copy of the Smart Tender Intelligence System. Open **this folder** in VS Code, then use its integrated terminal to run:

```bash
chmod +x run-tenderiq.sh
./run-tenderiq.sh
```

The first run downloads project-local Node.js and Python runtimes and installs dependencies; no Homebrew is required. Then open [http://localhost:5173](http://localhost:5173).

To enable live AI tender analysis, create a `.env` file from `.env.example` and set `OPENAI_API_KEY`. Without a key, PDF intake still works using the local heuristic extraction path.

Use `Ctrl+C` in the terminal to stop both the frontend and the API.

## Project layout

- `frontend/` — React + TypeScript tender intelligence dashboard
- `backend/` — FastAPI PDF extraction, structured LLM analysis, RAG-ready API
- `docker-compose.yml` — optional PostgreSQL database

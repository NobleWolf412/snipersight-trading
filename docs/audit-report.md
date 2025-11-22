# Frontend/Backend Integration Audit

## Critical integration issues

1. **Frontend API base URL targets the wrong port.** The UI defaults to `http://localhost:3000`, but the FastAPI server in `backend/api_server.py` launches on port 8000. Without overriding `VITE_API_URL`, every telemetry request will fail to reach the backend. Align the frontend default with the backend port or expose the server on 3000 to avoid cross-service connection errors.
2. **Telemetry filters pass raw strings where datetimes are expected.** The `/api/telemetry/events` endpoint forwards `start_time` and `end_time` query strings directly to the telemetry store, which calls `.isoformat()` on them. If a frontend filter is supplied, this raises an `AttributeError` and returns 500 instead of results. Parse the query params to `datetime` objects (or relax the store to accept strings) before calling `get_events`/`get_event_count`.

## Additional observations

- The repository ships two FastAPI entry points (`backend/api.py` and `backend/api_server.py`) with overlapping routes but different implementations. Make sure the deployment path is consistent so the UI hits the fully implemented telemetry endpoints in `api_server.py` and not the stubbed versions in `api.py`.
- Consider wiring the scanner endpoints to real data or mock fixtures; currently several endpoints (e.g., `/api/scan`) return empty arrays, which will surface as blank UI states.

## Optimization ideas

- Normalize API configuration by exporting a single source of truth (e.g., `.env`-driven URL and port) to reduce drift between services.
- Harden telemetry filtering by validating query parameters and returning structured error messages to avoid silent polling failures in the activity feed.


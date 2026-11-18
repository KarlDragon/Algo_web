# AlgoVisual frontend

React + TypeScript + Vite frontend for the FastAPI backend.

## Run locally

Start the backend from `BE`:

```powershell
python -m uvicorn main:app --reload
```

Start the frontend from `FE`:

```powershell
npm install
npm run dev
```

Vite proxies `/api/*` to `http://127.0.0.1:8000/*` and strips the `/api`
prefix. Change the proxy target in `vite.config.ts` when the backend uses
another address.

## Backend integration

The frontend calls the implemented FastAPI routes using JSON snake_case fields:

- Authentication: `POST /auth/register`, `/auth/login`, `/auth/refresh`, and
  `/auth/logout`
- Session/profile: `GET /users/me`, `PATCH /users/me`
- Home and content: `GET /home`, `/categories`, `/algorithms`, and
  `/algorithms/{slug}`
- Search and saved algorithms: `GET /search`, `/search/suggestions`, and
  `/users/me/favorites`
- Learning interactions: algorithm progress, favorites, comments, and ratings

Access and rotating refresh tokens are saved in browser storage. Protected API
requests include the access token; on `401`, the client attempts one refresh and
retries the original request. If refresh fails, the session is cleared and the
login/register screen is shown.

The simulator runs supported sorting, searching, BFS, and DFS visualizations in
the browser. It does not call a simulation endpoint.

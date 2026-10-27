# Algo Web frontend

React + TypeScript account forms for the FastAPI authentication endpoints.

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

The Vite development server proxies `/api/*` to `http://127.0.0.1:8000/*`.
Change the proxy target in `vite.config.ts` if the backend uses another address.

## Authentication API

- `POST /register` sends `{ "username", "password", "email" }` and expects
  `{ "id", "username", "email" }`.
- `POST /login` sends `{ "login", "password" }`, where `login` is a username or
  email. It expects `{ "message", "access_token", "token_type", "user" }`.

The registration form mirrors the backend's username, password, and email
constraints. Login errors and registration errors returned by FastAPI are shown
in the form.

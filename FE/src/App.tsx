import { useState, type FormEvent } from 'react'
import './App.css'

type Mode = 'login' | 'register'

type User = {
  id: number
  username: string
  email: string
}

type LoginResponse = {
  message: string
  access_token: string
  token_type: string
  user: User
}

type RegisterResponse = User

type FormStatus =
  | { kind: 'error'; message: string }
  | { kind: 'login-success'; message: string; user: User }
  | { kind: 'register-success'; user: User }

function isUser(value: unknown): value is User {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const user = value as Record<string, unknown>

  return (
    typeof user.id === 'number' &&
    typeof user.username === 'string' &&
    typeof user.email === 'string'
  )
}

function isLoginResponse(value: unknown): value is LoginResponse {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const response = value as Record<string, unknown>

  return (
    typeof response.message === 'string' &&
    typeof response.access_token === 'string' &&
    typeof response.token_type === 'string' &&
    isUser(response.user)
  )
}

function isRegisterResponse(value: unknown): value is RegisterResponse {
  return isUser(value)
}

function getErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = payload.detail

    if (typeof detail === 'string') {
      return detail
    }

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (
            typeof item === 'object' &&
            item !== null &&
            'msg' in item &&
            typeof item.msg === 'string'
          ) {
            return item.msg
          }

          return null
        })
        .filter((message): message is string => message !== null)

      if (messages.length > 0) {
        return messages.join(' ')
      }
    }
  }

  return `Request failed with status ${status}. Please try again.`
}

async function postJson(path: string, body: Record<string, string>) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  let payload: unknown

  try {
    payload = await response.json()
  } catch {
    throw new Error('The server returned an invalid response.')
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(payload, response.status))
  }

  return payload
}

function App() {
  const [mode, setMode] = useState<Mode>('login')
  const [status, setStatus] = useState<FormStatus | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function changeMode(nextMode: Mode) {
    setMode(nextMode)
    setStatus(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setStatus(null)
    setIsSubmitting(true)

    const formData = new FormData(event.currentTarget)

    try {
      if (mode === 'login') {
        const payload = await postJson('/api/login', {
          login: String(formData.get('login') ?? ''),
          password: String(formData.get('password') ?? ''),
        })

        if (!isLoginResponse(payload)) {
          throw new Error('The server returned an unexpected login response.')
        }

        setStatus({
          kind: 'login-success',
          message: payload.message,
          user: payload.user,
        })
      } else {
        const payload = await postJson('/api/register', {
          username: String(formData.get('username') ?? ''),
          password: String(formData.get('password') ?? ''),
          email: String(formData.get('email') ?? ''),
        })

        if (!isRegisterResponse(payload)) {
          throw new Error('The server returned an unexpected registration response.')
        }

        setStatus({
          kind: 'register-success',
          user: payload,
        })
      }
    } catch (error) {
      setStatus({
        kind: 'error',
        message:
          error instanceof TypeError
            ? 'Could not connect to the server. Check that the backend is running and try again.'
            : error instanceof Error
              ? error.message
              : 'Something went wrong. Please try again.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const isRegistering = mode === 'register'

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <header className="auth-header">
          <h1 id="auth-title">{isRegistering ? 'Create account' : 'Welcome back'}</h1>
          <p>
            {isRegistering
              ? 'Enter your details to get started.'
              : 'Sign in with your username or email.'}
          </p>
        </header>

        <div className="auth-tabs" role="group" aria-label="Account action">
          <button
            aria-pressed={!isRegistering}
            className={!isRegistering ? 'auth-tab is-active' : 'auth-tab'}
            disabled={isSubmitting}
            onClick={() => changeMode('login')}
            type="button"
          >
            Log in
          </button>
          <button
            aria-pressed={isRegistering}
            className={isRegistering ? 'auth-tab is-active' : 'auth-tab'}
            disabled={isSubmitting}
            onClick={() => changeMode('register')}
            type="button"
          >
            Register
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {isRegistering ? (
            <>
              <div className="form-field">
                <label htmlFor="username">Username</label>
                <input
                  autoComplete="username"
                  id="username"
                  maxLength={50}
                  name="username"
                  pattern="(?=.*[A-Za-z])(?=.*[0-9]).*"
                  required
                  aria-describedby="username-hint"
                  title="Use at least one letter and one number."
                />
                <span className="field-hint" id="username-hint">
                  Up to 50 characters; include at least one letter and one number.
                </span>
              </div>

              <div className="form-field">
                <label htmlFor="email">Email</label>
                <input
                  autoComplete="email"
                  id="email"
                  maxLength={100}
                  name="email"
                  pattern="[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
                  required
                  type="email"
                />
              </div>

              <div className="form-field">
                <label htmlFor="register-password">Password</label>
                <input
                  autoComplete="new-password"
                  id="register-password"
                  maxLength={64}
                  minLength={8}
                  name="password"
                  pattern="(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,64}"
                  required
                  aria-describedby="password-hint"
                  title="Use 8–64 characters, including an uppercase letter, a number, and a special character."
                  type="password"
                />
                <span className="field-hint" id="password-hint">
                  8–64 characters, with an uppercase letter, a number, and a special
                  character.
                </span>
              </div>
            </>
          ) : (
            <>
              <div className="form-field">
                <label htmlFor="login">Username or email</label>
                <input
                  autoComplete="username"
                  id="login"
                  name="login"
                  required
                />
              </div>

              <div className="form-field">
                <label htmlFor="login-password">Password</label>
                <input
                  autoComplete="current-password"
                  id="login-password"
                  name="password"
                  required
                  type="password"
                />
              </div>
            </>
          )}

          {status?.kind === 'error' && (
            <p className="form-status is-error" role="alert">
              {status.message}
            </p>
          )}

          <button className="submit-button" disabled={isSubmitting} type="submit">
            {isSubmitting
              ? 'Please wait…'
              : isRegistering
                ? 'Create account'
                : 'Log in'}
          </button>
        </form>

        {status?.kind === 'login-success' && (
          <div className="form-status is-success" role="status">
            <p>{status.message}</p>
            <p>
              Signed in as <strong>{status.user.username}</strong> ({status.user.email})
            </p>
          </div>
        )}

        {status?.kind === 'register-success' && (
          <div className="form-status is-success" role="status">
            <p>
              Account created for <strong>{status.user.username}</strong> (
              {status.user.email}).
            </p>
            <button
              className="text-button"
              onClick={() => changeMode('login')}
              type="button"
            >
              Continue to log in
            </button>
          </div>
        )}
      </section>
    </main>
  )
}

export default App

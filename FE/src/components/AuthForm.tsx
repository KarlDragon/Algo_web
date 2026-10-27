import type { FormEvent } from 'react'
import type {
  AuthMode,
  AuthStatus,
  AuthSubmission,
} from '../models/auth'
import LoginFields from './LoginFields'
import RegisterFields from './RegisterFields'

type AuthFormProps = {
  isSubmitting: boolean
  mode: AuthMode
  onModeChange: (mode: AuthMode) => void
  onSubmit: (submission: AuthSubmission) => Promise<void>
  status: AuthStatus | null
}

function AuthForm({
  isSubmitting,
  mode,
  onModeChange,
  onSubmit,
  status,
}: AuthFormProps) {
  const isRegistering = mode === 'register'

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const formData = new FormData(event.currentTarget)

    if (mode === 'login') {
      void onSubmit({
        mode: 'login',
        data: {
          login: String(formData.get('login') ?? ''),
          password: String(formData.get('password') ?? ''),
        },
      })
      return
    }

    void onSubmit({
      mode: 'register',
      data: {
        username: String(formData.get('username') ?? ''),
        password: String(formData.get('password') ?? ''),
        email: String(formData.get('email') ?? ''),
      },
    })
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <header className="auth-header">
          <h1 id="auth-title">
            {isRegistering ? 'Tạo tài khoản mới' : 'Chào mừng!'}
          </h1>
          <p>
            {isRegistering
              ? 'Vui lòng nhập thông tin.'
              : 'Tên đăng nhập hoặc email.'}
          </p>
        </header>

        <div className="auth-tabs" role="group" aria-label="Account action">
          <button
            aria-pressed={!isRegistering}
            className={!isRegistering ? 'auth-tab is-active' : 'auth-tab'}
            disabled={isSubmitting}
            onClick={() => onModeChange('login')}
            type="button"
          >
            Đăng nhập
          </button>
          <button
            aria-pressed={isRegistering}
            className={isRegistering ? 'auth-tab is-active' : 'auth-tab'}
            disabled={isSubmitting}
            onClick={() => onModeChange('register')}
            type="button"
          >
            Đăng ký
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {isRegistering ? <RegisterFields /> : <LoginFields />}

          {status?.kind === 'error' && (
            <p className="form-status is-error" role="alert">
              {status.message}
            </p>
          )}

          <button className="submit-button" disabled={isSubmitting} type="submit">
            {isSubmitting
              ? 'Chờ trong giây lát…'
              : isRegistering
                ? 'Đăng ký'
                : 'Đăng nhập'}
          </button>
        </form>

        {status?.kind === 'login-success' && (
          <div className="form-status is-success" role="status">
            <p>{status.message}</p>
            <p>
              Signed in as <strong>{status.user.username}</strong> (
              {status.user.email})
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
              onClick={() => onModeChange('login')}
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

export default AuthForm

import { useEffect, useState } from 'react'
import './App.css'
import AuthForm from './components/AuthForm'
import LearningWorkspace from './components/LearningWorkspace'
import NightSkyCanvas from './components/NightSkyCanvas'
import { useAuth } from './hooks/useAuth'
import type { AuthMode } from './models/auth'
import type { UserProfile } from './models/api'
import { getMe } from './services/contentService'
import { hasSession } from './services/apiClient'

function App() {
  const [mode, setMode] = useState<AuthMode>('login')
  const [user, setUser] = useState<UserProfile | null>(null)
  const [isCheckingSession, setIsCheckingSession] = useState(true)
  const [sessionError, setSessionError] = useState('')
  const { status, isSubmitting, submit, clearStatus } = useAuth()

  useEffect(() => {
    let active = true
    const onExpired = () => {
      if (active) {
        setUser(null)
        setMode('login')
        setSessionError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
        clearStatus()
      }
    }
    window.addEventListener('algo:session-expired', onExpired)

    if (!hasSession()) {
      setIsCheckingSession(false)
    } else {
      getMe()
        .then((profile) => {
          if (active) setUser(profile)
        })
        .catch((error: unknown) => {
          if (active) {
            setSessionError(
              error instanceof Error ? error.message : 'Không thể khôi phục phiên đăng nhập.',
            )
          }
        })
        .finally(() => {
          if (active) setIsCheckingSession(false)
        })
    }

    return () => {
      active = false
      window.removeEventListener('algo:session-expired', onExpired)
    }
  }, [clearStatus])

  useEffect(() => {
    if (status?.kind !== 'login-success') return
    let active = true
    setIsCheckingSession(true)
    getMe()
      .then((profile) => {
        if (active) {
          setUser(profile)
          setSessionError('')
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setUser({
            ...status.user,
            full_name: null,
            avatar_url: null,
            created_at: '',
          })
          setSessionError(
            error instanceof Error ? error.message : 'Không thể tải hồ sơ tài khoản.',
          )
        }
      })
      .finally(() => {
        if (active) setIsCheckingSession(false)
      })
    return () => {
      active = false
    }
  }, [status])

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode)
    clearStatus()
  }

  function handleLogout(error = '') {
    setUser(null)
    setMode('login')
    setSessionError(error)
    clearStatus()
  }

  if (isCheckingSession) {
    return (
      <main className="session-loading" role="status">
        <span className="loading-spinner" />
        Đang kiểm tra phiên đăng nhập…
      </main>
    )
  }

  if (user) {
    return (
      <LearningWorkspace
        onLogout={async (error) => handleLogout(error)}
        onProfileChange={setUser}
        user={user}
      />
    )
  }

  return (
    <>
      <NightSkyCanvas />
      {sessionError && <p className="session-error" role="alert">{sessionError}</p>}
      <AuthForm
        isSubmitting={isSubmitting}
        mode={mode}
        onModeChange={changeMode}
        onSubmit={submit}
        status={status}
      />
    </>
  )
}

export default App

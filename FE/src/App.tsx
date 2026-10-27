import { useState } from 'react'
import './App.css'
import AuthForm from './components/AuthForm'
import NightSkyCanvas from './components/NightSkyCanvas'
import { useAuth } from './hooks/useAuth'
import type { AuthMode } from './models/auth'

function App() {
  const [mode, setMode] = useState<AuthMode>('login')
  const { status, isSubmitting, submit, clearStatus } = useAuth()

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode)
    clearStatus()
  }

  return (
    <>
      <NightSkyCanvas />
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

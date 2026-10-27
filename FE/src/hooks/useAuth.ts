import { useState } from 'react'
import type { AuthStatus, AuthSubmission } from '../models/auth'
import { login, register } from '../services/authService'

function getSubmissionError(error: unknown): string {
  if (error instanceof TypeError) {
    return 'Could not connect to the server. Check that the backend is running and try again.'
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Something went wrong. Please try again.'
}

export function useAuth() {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function submit(submission: AuthSubmission): Promise<void> {
    setStatus(null)
    setIsSubmitting(true)

    try {
      if (submission.mode === 'login') {
        const response = await login(submission.data)

        setStatus({
          kind: 'login-success',
          message: response.message,
          user: response.user,
        })
      } else {
        const user = await register(submission.data)
        setStatus({ kind: 'register-success', user })
      }
    } catch (error) {
      setStatus({ kind: 'error', message: getSubmissionError(error) })
    } finally {
      setIsSubmitting(false)
    }
  }

  function clearStatus() {
    setStatus(null)
  }

  return { status, isSubmitting, submit, clearStatus }
}

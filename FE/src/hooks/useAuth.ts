import { useCallback, useState } from 'react'
import type { AuthStatus, AuthSubmission } from '../models/auth'
import { login, register } from '../services/authService'

function getSubmissionError(error: unknown): string {
  if (error instanceof TypeError) {
    return 'Không thể kết nối máy chủ. Hãy kiểm tra backend đang chạy rồi thử lại.'
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Đã xảy ra lỗi. Vui lòng thử lại.'
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

  const clearStatus = useCallback(() => {
    setStatus(null)
  }, [])

  return { status, isSubmitting, submit, clearStatus }
}

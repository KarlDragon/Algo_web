import type { AuthTokens } from '../models/api'

const SESSION_KEY = 'algo-web-session'

export class ApiError extends Error {
  readonly status: number

  constructor(
    message: string,
    status: number,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type Session = Pick<AuthTokens, 'access_token' | 'refresh_token'>

function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const value: unknown = JSON.parse(raw)
    if (
      typeof value === 'object' &&
      value !== null &&
      'access_token' in value &&
      'refresh_token' in value &&
      typeof value.access_token === 'string' &&
      typeof value.refresh_token === 'string'
    ) {
      return { access_token: value.access_token, refresh_token: value.refresh_token }
    }
  } catch {
    localStorage.removeItem(SESSION_KEY)
  }
  return null
}

export function saveSession(tokens: Session): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(tokens))
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_KEY)
}

export function hasSession(): boolean {
  return readSession() !== null
}

export function getStoredRefreshToken(): string | null {
  return readSession()?.refresh_token ?? null
}

function announceExpiredSession(): void {
  clearSession()
  window.dispatchEvent(new CustomEvent('algo:session-expired'))
}

function errorMessage(payload: unknown, status: number): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = payload.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item) =>
        typeof item === 'object' &&
        item !== null &&
        'msg' in item &&
        typeof item.msg === 'string'
          ? [item.msg]
          : [],
      )
      if (messages.length) return messages.join(' ')
    }
  }
  return `Yêu cầu không thành công (mã ${status}). Vui lòng thử lại.`
}

async function readResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const text = await response.text()
  if (!text) return undefined
  try {
    return JSON.parse(text) as unknown
  } catch {
    throw new ApiError('Máy chủ trả về dữ liệu không hợp lệ.', response.status)
  }
}

let refreshInFlight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    const session = readSession()
    if (!session) return null
    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    })
    const payload = await readResponse(response)
    if (!response.ok) {
      if (response.status === 401) {
        announceExpiredSession()
        return null
      }
      throw new ApiError(errorMessage(payload, response.status), response.status)
    }
    if (
      typeof payload !== 'object' ||
      payload === null ||
      !('access_token' in payload) ||
      !('refresh_token' in payload) ||
      typeof payload.access_token !== 'string' ||
      typeof payload.refresh_token !== 'string'
    ) {
      throw new ApiError('Máy chủ trả về phiên đăng nhập không hợp lệ.', response.status)
    }
    saveSession({
      access_token: payload.access_token,
      refresh_token: payload.refresh_token,
    })
    return payload.access_token
  })()
  try {
    return await refreshInFlight
  } finally {
    refreshInFlight = null
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const session = authenticated ? readSession() : null
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`)
  }

  let response = await fetch(`/api${path}`, { ...init, headers })
  let retriedAfterRefresh = false
  if (response.status === 401 && authenticated && session) {
    const newAccessToken = await refreshAccessToken()
    if (newAccessToken) {
      const retryHeaders = new Headers(headers)
      retryHeaders.set('Authorization', `Bearer ${newAccessToken}`)
      response = await fetch(`/api${path}`, { ...init, headers: retryHeaders })
      retriedAfterRefresh = true
    }
  }

  const payload = await readResponse(response)
  if (!response.ok) {
    if (response.status === 401 && authenticated && (!session || retriedAfterRefresh)) {
      announceExpiredSession()
    }
    throw new ApiError(errorMessage(payload, response.status), response.status)
  }
  return payload as T
}

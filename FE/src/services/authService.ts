import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  User,
} from '../models/auth'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isUser(value: unknown): value is User {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.id === 'number' &&
    typeof value.username === 'string' &&
    typeof value.email === 'string'
  )
}

function isLoginResponse(value: unknown): value is LoginResponse {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.message === 'string' &&
    typeof value.access_token === 'string' &&
    typeof value.token_type === 'string' &&
    isUser(value.user)
  )
}

function getErrorMessage(payload: unknown, status: number): string {
  if (isRecord(payload) && 'detail' in payload) {
    const { detail } = payload

    if (typeof detail === 'string') {
      return detail
    }

    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item) =>
        isRecord(item) && typeof item.msg === 'string' ? [item.msg] : [],
      )

      if (messages.length > 0) {
        return messages.join(' ')
      }
    }
  }

  return `Request failed with status ${status}. Please try again.`
}

async function postJson(
  path: string,
  body: LoginRequest | RegisterRequest,
): Promise<unknown> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const payload = await postJson('/api/login', data)

  if (!isLoginResponse(payload)) {
    throw new Error('The server returned an unexpected login response.')
  }

  return payload
}

export async function register(data: RegisterRequest): Promise<User> {
  const payload = await postJson('/api/register', data)

  if (!isUser(payload)) {
    throw new Error('The server returned an unexpected registration response.')
  }

  return payload
}

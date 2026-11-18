import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  User,
} from '../models/auth'
import { apiRequest, saveSession } from './apiClient'

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
    typeof value.refresh_token === 'string' &&
    typeof value.expires_in === 'number' &&
    typeof value.token_type === 'string' &&
    isUser(value.user)
  )
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const payload: unknown = await apiRequest(
    '/auth/login',
    { method: 'POST', body: JSON.stringify(data) },
    false,
  )

  if (!isLoginResponse(payload)) {
    throw new Error('Máy chủ trả về dữ liệu đăng nhập không hợp lệ.')
  }

  saveSession(payload)
  return payload
}

export async function register(data: RegisterRequest): Promise<User> {
  const payload: unknown = await apiRequest(
    '/auth/register',
    { method: 'POST', body: JSON.stringify(data) },
    false,
  )

  if (!isUser(payload)) {
    throw new Error('Máy chủ trả về dữ liệu đăng ký không hợp lệ.')
  }

  return payload
}

export type AuthMode = 'login' | 'register'

export type User = {
  id: number
  username: string
  email: string
}

export type LoginRequest = {
  login: string
  password: string
}

export type RegisterRequest = {
  username: string
  password: string
  email: string
}

export type LoginResponse = {
  message: string
  access_token: string
  token_type: string
  user: User
}

export type AuthSubmission =
  | { mode: 'login'; data: LoginRequest }
  | { mode: 'register'; data: RegisterRequest }

export type AuthStatus =
  | { kind: 'error'; message: string }
  | { kind: 'login-success'; message: string; user: User }
  | { kind: 'register-success'; user: User }

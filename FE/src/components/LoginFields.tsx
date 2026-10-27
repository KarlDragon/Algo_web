function LoginFields() {
  return (
    <>
      <div className="form-field">
        <label htmlFor="login">Tên đăng nhập hoặc email</label>
        <input
          autoComplete="username"
          id="login"
          name="login"
          required
        />
      </div>

      <div className="form-field">
        <label htmlFor="login-password">Mật khẩu</label>
        <input
          autoComplete="current-password"
          id="login-password"
          name="password"
          required
          type="password"
        />
      </div>
    </>
  )
}

export default LoginFields

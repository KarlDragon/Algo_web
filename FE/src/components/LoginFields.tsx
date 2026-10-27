function LoginFields() {
  return (
    <>
      <div className="form-field">
        <label htmlFor="login">Username or email</label>
        <input
          autoComplete="username"
          id="login"
          name="login"
          required
        />
      </div>

      <div className="form-field">
        <label htmlFor="login-password">Password</label>
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

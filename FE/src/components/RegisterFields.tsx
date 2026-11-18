function RegisterFields() {
  return (
    <>
      <div className="form-field">
        <label htmlFor="username">Tên đăng nhập</label>
        <input
          aria-describedby="username-hint"
          autoComplete="username"
          id="username"
          maxLength={50}
          minLength={3}
          name="username"
          pattern="[A-Za-z0-9_]{3,50}"
          required
          title="Tên đăng nhập gồm 3–50 ký tự: chữ cái không dấu, số hoặc dấu gạch dưới."
        />
        <span className="field-hint" id="username-hint">
          Từ 3–50 ký tự; chỉ dùng chữ cái không dấu, số và dấu gạch dưới.
        </span>
      </div>

      <div className="form-field">
        <label htmlFor="email">Email</label>
        <input
          autoComplete="email"
          id="email"
          maxLength={100}
          name="email"
          pattern="[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
          required
          type="email"
        />
      </div>

      <div className="form-field">
        <label htmlFor="register-password">Mật khẩu</label>
        <input
          aria-describedby="password-hint"
          autoComplete="new-password"
          id="register-password"
          maxLength={64}
          minLength={8}
          name="password"
          pattern="(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,64}"
          required
          title="Mật khẩu ít nhất 8 ký tự, có chữ cái in hoa, số và ký tự đặc biệt"
          type="password"
        />
        <span className="field-hint" id="password-hint">
          Mật khẩu ít nhất 8 ký tự, có chữ cái in hoa, số và ký tự đặc biệt
        </span>
      </div>
    </>
  )
}

export default RegisterFields

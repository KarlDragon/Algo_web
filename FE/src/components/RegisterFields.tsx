function RegisterFields() {
  return (
    <>
      <div className="form-field">
        <label htmlFor="username">Username</label>
        <input
          aria-describedby="username-hint"
          autoComplete="username"
          id="username"
          maxLength={50}
          name="username"
          pattern="(?=.*[A-Za-z])(?=.*[0-9]).*"
          required
          title="Use at least one letter and one number."
        />
        <span className="field-hint" id="username-hint">
          Up to 50 characters; include at least one letter and one number.
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
        <label htmlFor="register-password">Password</label>
        <input
          aria-describedby="password-hint"
          autoComplete="new-password"
          id="register-password"
          maxLength={64}
          minLength={8}
          name="password"
          pattern="(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,64}"
          required
          title="Use 8–64 characters, including an uppercase letter, a number, and a special character."
          type="password"
        />
        <span className="field-hint" id="password-hint">
          8–64 characters, with an uppercase letter, a number, and a special
          character.
        </span>
      </div>
    </>
  )
}

export default RegisterFields

# Algo_web — Auth mục 1 (chỉ Backend)

> Dựa trên source nhánh `main` ngày 13/11/2026 và 4 file Auth bước 1 đã áp dụng ở `feature/auth-be-step1`. Không đụng FE. Không chứa `.env`, `users.db`, JWT secret hay thông tin SMTP.

## Phạm vi đã code

- 1.1 `POST /auth/register`: validate 400, username 3–50 ký tự `[A-Za-z0-9_]` + có ít nhất 1 chữ và 1 số, email chữ thường, 409 trùng, role USER mặc định, gửi email chào mừng ở background sau commit.
- 1.2 `POST /auth/login`: username/email + password Argon2, role trong access token và user response, `refresh_token`, `expires_in`, `remember_me` (mặc định false). Giới hạn 5 lần / 15 phút trên mỗi IP và tên đăng nhập; đồng thời hạn chế tổng request theo IP.
- 1.3 `POST /auth/refresh`: refresh token opaque (băm SHA-256 khi lưu), xoay vòng token, token cũ không sử dụng lại được. Replay token đã xoay vòng sẽ thu hồi toàn phiên.
- 1.4 `POST /auth/logout`: Bearer access token bắt buộc, thu hồi refresh token family.
- 1.5 `POST /auth/forgot-password`: trả cùng kết quả dù email có tồn tại hay không; token 20 phút, chỉ lưu hash, email chứa link reset.
- 1.6 `POST /auth/reset-password`: token một lần, validate mật khẩu, đổi password và thu hồi mọi refresh token user, email xác nhận.
- 1.7 `POST /auth/change-password`: Bearer bắt buộc, xác minh mật khẩu hiện tại, đổi và thu hồi refresh token, email xác nhận.
- Shared: `get_current_user` và `require_admin` được đặt trong `Services/AuthDependencies.py`, có thể dùng cho `Users/Algorithms` ở TODO mục 2+. `main.py` trả lỗi validation JSON 400 dạng `{ "detail": "..." }`.

## Chuẩn bị và cài đặt — PowerShell (chạy trong root Algo_web-latest)

**Không đổi nhánh main, không chạy git add .** Giữ branch đang làm `feature/auth-be-step1`. Nếu đã tạo PR thì các commit mới trên branch này sẽ cập nhật PR. Nếu nhóm trưởng muốn nhiệm vụ này tách PR mới, hãy thống nhất trước khi push.

1. **Dừng Uvicorn** với `Ctrl+C` và tắt tab đang mở `users.db` trong SQLite Viewer.
2. **Sao lưu database ra ngoài repository** trước khi thay schema:

   ```powershell
   Set-Location -LiteralPath 'C:\Users\Admin\OneDrive - ut.edu.vn\Documents\Algo_web-latest'
   git status --short --branch
   if (Test-Path .\BE\users.db) {
       Copy-Item .\BE\users.db (Join-Path $HOME ("users-backup-" + (Get-Date -Format yyyyMMdd-HHmmss) + ".db"))
   }
   ```

3. Giải nén ZIP vào **thư mục gốc `Algo_web-latest`** (ZIP có thư mục `BE/` bên trong). Ví dụ nếu tải file về `Downloads`:

   ```powershell
   Expand-Archive -LiteralPath "$HOME\Downloads\Algo_web_BE_Auth_Muc1.zip" -DestinationPath . -Force
   ```

   Nếu máy lưu file ở nơi khác, đổi lại đường dẫn đúng. Chỉ có file trong `BE/` được ghi đè, không tác động FE.

4. Thư viện cần thiết:

   ```powershell
   py -m pip install -r .\BE\requirements.txt
   py -m pip install pytest httpx
   ```

5. Trong `BE/.env` giữ các biến đã có, không gửi secret cho ai. Để gửi email thật, bổ sung theo nhà cung cấp SMTP:

   ```dotenv
   DATABASE_URL=sqlite:///./users.db
   SQLALCHEMY_ECHO=false
   JWT_SECRET_KEY=<SECRET_RIENG_CUA_BAN>
   JWT_ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   SMTP_HOST=<SMTP_SERVER>
   SMTP_PORT=587
   SMTP_SSL=false
   SMTP_USERNAME=<SMTP_LOGIN>
   SMTP_PASSWORD=<SMTP_APP_PASSWORD>
   SMTP_FROM=<EMAIL_NGUOI_GUI>
   FRONTEND_RESET_PASSWORD_URL=http://localhost:5173/reset-password
   ```

   Nếu chưa có SMTP, chỉ cần giữ các biến DATABASE_URL/JWT cũ; API Auth vẫn chạy, nhưng **không gửi được email**. Link reset cần trỏ tới trang reset mật khẩu thật khi FE làm xong. Không lưu mật khẩu SMTP trong code hoặc Git.

6. **Migration bắt buộc** (từ thư mục `BE`, chỉ chạy một lần cho mỗi database):

   ```powershell
   Set-Location .\BE
   py -m alembic -c alembic.ini upgrade head
   py -m alembic -c alembic.ini current
   ```

   Migration giữ tài khoản cũ, thêm `role`, `fullName`, `avatarUrl`, `createdAt`; tạo `refresh_tokens`, `password_reset_tokens`. Nếu email cũ chỉ khác hoa/thường mà bị trùng, migration từ chối để bạn giải quyết trước, **không xóa data**. Nếu dùng DB khác SQLite thì cần review migration trước.

7. Test + chạy server:

   ```powershell
   py -m pytest tests -q
   py -m uvicorn main:app --reload
   ```

   Swagger: `http://127.0.0.1:8000/docs`.

## Thứ tự kiểm thử Swagger

- `/auth/register` (201) `{"username":"user2026","password":"Test@2026","email":"USER2026@example.com"}`. Response có `role: USER`, email chữ thường.
- `/auth/login` (200) `{"login":"user2026","password":"Test@2026","remember_me":false}`. Có `access_token`, `refresh_token`, `expires_in`.
- Nhấn **Authorize**, nhập access token theo giao diện Swagger (không chia sẻ token).
- `/auth/refresh` (200) `{"refresh_token":"<token_vua_nhan>"}`: nhận refresh mới; dùng refresh cũ lần nữa sẽ 401 và thu hồi phiên.
- `/auth/logout` (200) `{"refresh_token":"<refresh_moi>"}` kèm Bearer. Sau đó refresh phải 401.
- `/auth/change-password` (200), Bearer, `{"current_password":"Test@2026","new_password":"New@2026","confirm_password":"New@2026"}`. Login bằng password cũ → 401, bằng password mới → 200.
- `/auth/forgot-password` (200) `{"email":"user2026@example.com"}`: cùng thông báo kể cả email không tồn tại. Lấy token **chỉ từ email thật**, không từ response.
- `/auth/reset-password` (200) `{"token":"<token_trong_email>","new_password":"Reset@2026","confirm_password":"Reset@2026"}`. Token đã dùng lại → 400.
- Thử login sai liên tiếp 6 lần với cùng tài khoản → lần thứ 6 được 429.

### Quy ước response

- Thành công: JSON object trực tiếp, `snake_case` theo TODO (ví dụ `refresh_token`, `expires_in`, `remember_me`, `new_password`).
- Lỗi: `{"detail":"Thông báo tiếng Việt"}`. Validation HTTP 400, sai auth 401, duplicate 409, rate limit 429.
- API mới `/auth/*` trên BE; qua Vite proxy, FE cần đổi thành `/api/auth/*`. **Không sửa FE trong gói này**.

## Giới hạn cần biết trước khi báo nhóm trưởng “hoàn thành”

1. Gói đã có code + migration + test, nhưng phải chạy thành công trên máy của bạn (gồm DB cũ) trước khi commit/PR.
2. MailService chỉ gửi được email thật sau khi có cấu hình SMTP chính xác; trang đặt lại mật khẩu của FE cũng cần được nhóm FE xây dựng.
3. `RateLimiter` đang lưu trong RAM, phù hợp một tiến trình local/dev; khi deploy nhiều worker/server phải chuyển sang Redis/shared store. Không dùng nguyên trạng để tuyên bố chống brute-force ở production.
4. Logout/đổi/reset mật khẩu thu hồi **refresh token**; access JWT đã phát hành vẫn có thể dùng đến khi hết hạn (theo thiết kế stateless JWT, tối đa theo `ACCESS_TOKEN_EXPIRE_MINUTES`). Cần thiết kế access-token revocation riêng nếu nhóm yêu cầu đăng xuất tức thì.
5. Chưa tạo mặc định ADMIN bằng username/password; chỉ có USER. Cần seed ADMIN an toàn và có quản lý quyền trong TODO mục 9 hoặc quy trình nhóm.
6. `GET /users/me` nằm ở TODO **mục 2**, không phải Auth mục 1, nên chưa có ở gói này. Dependency JWT đã sẵn sàng cho mục 2.

## Git sau khi test thành công

Quay lại `Algo_web-latest`, kiểm tra danh sách file thay đổi. Stage **chỉ BE**:

```powershell
Set-Location -LiteralPath 'C:\Users\Admin\OneDrive - ut.edu.vn\Documents\Algo_web-latest'
git status --short --branch
git diff --check
git add BE/Controllers BE/Models BE/Repositories BE/Schemas BE/Services BE/main.py BE/database.py BE/requirements.txt BE/alembic.ini BE/alembic BE/tests BE/HUONG_DAN_AUTH_MUC1.md
git diff --cached --name-only
git diff --cached --check
```

Nếu danh sách stage **không có FE, `.env`, `users.db`** và kiểm thử đạt, mới chạy:

```powershell
git commit -m "feat(auth): complete authentication module with refresh and password recovery"
git push -u origin feature/auth-be-step1
```

Sau đó tạo/cập nhật PR vào `main`, đợi nhóm trưởng review; **không tự merge**.

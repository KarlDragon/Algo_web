import { appAuth, validOrigin } from '@/lib/app-auth'
import { getPayloadClient } from '@/lib/payload'

const safeUser = (user: NonNullable<Awaited<ReturnType<typeof appAuth.currentUser>>>) => ({
  id: user.id,
  name: user.name,
  email: user.email,
  bio: user.bio,
  speed: user.speed,
  reduceMotion: user.reduceMotion,
})
export async function GET() {
  const user = await appAuth.currentUser()
  return Response.json(
    { user: user ? safeUser(user) : null },
    { headers: { 'Cache-Control': 'private, no-store' } },
  )
}
export async function POST(request: Request) {
  if (!validOrigin(request))
    return Response.json({ error: 'Yêu cầu không hợp lệ.' }, { status: 403 })
  try {
    const data = await request.json()
    if (data.action === 'logout') {
      await appAuth.logout()
      return Response.json({ user: null })
    }
    const email = typeof data.email === 'string' ? data.email.trim().toLowerCase() : ''
    const password = typeof data.password === 'string' ? data.password : ''
    if (
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ||
      email.length > 254 ||
      password.length < 8 ||
      password.length > 128
    )
      return Response.json(
        { error: 'Nhập email hợp lệ và mật khẩu từ 8–128 ký tự.' },
        { status: 400 },
      )
    if (data.action === 'register') {
      const name = typeof data.name === 'string' ? data.name.trim() : ''
      if (name.length < 2 || name.length > 60)
        return Response.json({ error: 'Tên cần có từ 2–60 ký tự.' }, { status: 400 })
      const payload = await getPayloadClient()
      await payload.create({
        collection: 'users',
        overrideAccess: false,
        data: { email, password, name },
      })
    } else if (data.action !== 'login')
      return Response.json({ error: 'Thao tác không hợp lệ.' }, { status: 400 })
    const user = await appAuth.login(email, password)
    return Response.json({ user: safeUser(user) })
  } catch {
    return Response.json(
      { error: 'Không thể đăng nhập hoặc tạo tài khoản. Kiểm tra thông tin và thử lại.' },
      { status: 400 },
    )
  }
}
export async function PATCH(request: Request) {
  if (!validOrigin(request))
    return Response.json({ error: 'Yêu cầu không hợp lệ.' }, { status: 403 })
  try {
    const user = await appAuth.currentUser()
    if (!user) return Response.json({ error: 'Vui lòng đăng nhập.' }, { status: 401 })
    const data = await request.json()
    const name = typeof data.name === 'string' ? data.name.trim() : user.name
    const bio = typeof data.bio === 'string' ? data.bio.trim() : user.bio
    const speed = data.speed ?? user.speed ?? 600
    const reduceMotion = data.reduceMotion ?? user.reduceMotion ?? false
    if (
      !name ||
      name.length < 2 ||
      name.length > 60 ||
      (bio?.length ?? 0) > 240 ||
      typeof speed !== 'number' ||
      speed < 80 ||
      speed > 1500 ||
      typeof reduceMotion !== 'boolean'
    )
      return Response.json({ error: 'Thông tin hồ sơ hoặc cài đặt không hợp lệ.' }, { status: 400 })
    const payload = await getPayloadClient()
    const updated = await payload.update({
      collection: 'users',
      id: user.id,
      user,
      overrideAccess: false,
      data: { name, bio, speed, reduceMotion },
    })
    return Response.json({ user: safeUser(updated) })
  } catch {
    return Response.json({ error: 'Chưa lưu được thay đổi. Vui lòng thử lại.' }, { status: 500 })
  }
}

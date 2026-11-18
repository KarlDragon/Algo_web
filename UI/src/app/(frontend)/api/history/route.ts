import { appAuth, validOrigin } from '@/lib/app-auth'
import { getPayloadClient } from '@/lib/payload'
import { algorithms } from '@/lib/algorithms'

export async function GET() {
  const user = await appAuth.currentUser()
  if (!user)
    return Response.json(
      { runs: [], quizAttempts: [] },
      { headers: { 'Cache-Control': 'private, no-store' } },
    )
  const payload = await getPayloadClient()
  const [runs, attempts] = await Promise.all([
    payload.find({
      collection: 'learning-runs',
      user,
      overrideAccess: false,
      where: { owner: { equals: user.id } },
      sort: '-createdAt',
      limit: 100,
      depth: 0,
    }),
    payload.find({
      collection: 'quiz-attempts',
      user,
      overrideAccess: false,
      where: { owner: { equals: user.id } },
      sort: '-createdAt',
      limit: 100,
      depth: 0,
    }),
  ])
  const quizAttempts = attempts.docs
    .filter((attempt) => attempt.result)
    .map((attempt) => {
      const result = attempt.result as {
        algorithmSlug?: string
        topicSlug: string
        topicTitle: string
        score: number
        percentage: number
        duration: number
      }
      return {
        id: attempt.id,
        algorithm: result.algorithmSlug ?? result.topicSlug,
        topicTitle: result.topicTitle,
        score: result.score,
        percentage: result.percentage,
        duration: result.duration,
        createdAt: attempt.createdAt,
        status: result.percentage >= 70 ? 'completed' : 'review',
      }
    })
  return Response.json(
    { runs: runs.docs, quizAttempts },
    { headers: { 'Cache-Control': 'private, no-store' } },
  )
}
export async function POST(request: Request) {
  if (!validOrigin(request))
    return Response.json({ error: 'Yêu cầu không hợp lệ.' }, { status: 403 })
  try {
    const user = await appAuth.currentUser()
    if (!user)
      return Response.json({ error: 'Đăng nhập để lưu quá trình học tập.' }, { status: 401 })
    const data = await request.json()
    if (
      !algorithms.some((a) => a.slug === data.algorithm) ||
      !Array.isArray(data.input) ||
      data.input.length < 2 ||
      data.input.length > 30 ||
      data.input.some((n: unknown) => !Number.isInteger(n) || Number(n) < 1 || Number(n) > 999)
    )
      return Response.json({ error: 'Mảng cần có 2–30 số nguyên từ 1 đến 999.' }, { status: 400 })
    const target = data.target ?? 42,
      start = data.start ?? 0
    if (
      !Number.isInteger(target) ||
      target < 1 ||
      target > 999 ||
      !Number.isInteger(start) ||
      start < 0 ||
      start > 5
    )
      return Response.json({ error: 'Tham số không hợp lệ.' }, { status: 400 })
    const payload = await getPayloadClient()
    await payload.create({
      collection: 'learning-runs',
      user,
      overrideAccess: false,
      data: { algorithm: data.algorithm, input: data.input, target, start, owner: user.id },
    })
    return Response.json({ success: true })
  } catch {
    return Response.json({ error: 'Không lưu được kết quả. Vui lòng thử lại.' }, { status: 500 })
  }
}

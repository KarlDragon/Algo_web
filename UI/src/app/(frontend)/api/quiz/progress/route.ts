import { appAuth } from '@/lib/app-auth'
import { getPayloadClient } from '@/lib/payload'
import { quizSummary, type QuizAttemptView, type QuizResult } from '@/lib/quiz'

export async function GET(request: Request) {
  const headers = { 'Cache-Control': 'private, no-store' }
  try {
    const id = new URL(request.url).searchParams.get('id')
    const user = await appAuth.currentUser()
    if (!user && id)
      return Response.json(
        { error: 'Vui lòng đăng nhập để xem kết quả đã lưu.' },
        { status: 401, headers },
      )
    if (!user)
      return Response.json({ attempts: [], summary: quizSummary([]), signedIn: false }, { headers })
    const payload = await getPayloadClient()
    if (id) {
      const { docs } = await payload.find({
        collection: 'quiz-attempts',
        user,
        overrideAccess: false,
        depth: 0,
        limit: 1,
        where: { and: [{ id: { equals: id } }, { owner: { equals: user.id } }] },
      })
      if (!docs[0])
        return Response.json(
          { error: 'Không tìm thấy kết quả hoặc bạn không có quyền xem.' },
          { status: 404, headers },
        )
      return Response.json({ id: docs[0].id, result: docs[0].result, saved: true }, { headers })
    }
    const attempts: QuizAttemptView[] = []
    let page = 1,
      more = true
    while (more) {
      const result = await payload.find({
        collection: 'quiz-attempts',
        user,
        overrideAccess: false,
        depth: 0,
        sort: '-createdAt',
        limit: 100,
        page,
        where: { owner: { equals: user.id } },
      })
      attempts.push(
        ...result.docs
          .filter((d) => d.result)
          .map((d) => ({ id: d.id, result: d.result as QuizResult, createdAt: d.createdAt })),
      )
      more = result.hasNextPage
      page++
    }
    // Full history contributes to statistics, while detailed review is fetched on demand.
    const summaries = attempts.map((a) => ({
      ...a,
      result: {
        ...a.result,
        review: a.result.review.map((q) => ({ id: q.id, correct: q.correct })),
      },
    }))
    return Response.json(
      { attempts: summaries, summary: quizSummary(attempts), signedIn: true },
      { headers },
    )
  } catch {
    return Response.json(
      { error: 'Không tải được tiến độ học tập. Vui lòng thử lại.' },
      { status: 500, headers },
    )
  }
}

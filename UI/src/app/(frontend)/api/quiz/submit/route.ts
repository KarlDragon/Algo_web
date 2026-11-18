import { appAuth, validOrigin } from '@/lib/app-auth'
import { getPayloadClient } from '@/lib/payload'
import { parseQuizSubmission } from '@/lib/quiz'
import { gradeQuizSubmission } from '@/lib/quiz-grading'

export async function POST(request: Request) {
  if (!validOrigin(request))
    return Response.json({ error: 'Yêu cầu không hợp lệ.' }, { status: 403 })
  try {
    const input = parseQuizSubmission(await request.json())
    const user = await appAuth.currentUser()
    const payload = await getPayloadClient()
    if (!user)
      return Response.json({ result: await gradeQuizSubmission(payload, input), saved: false })
    const existing = await payload.find({
      collection: 'quiz-attempts',
      user,
      overrideAccess: false,
      depth: 0,
      limit: 1,
      where: {
        and: [{ submissionId: { equals: input.submissionId } }, { owner: { equals: user.id } }],
      },
    })
    if (existing.docs[0])
      return Response.json({
        id: existing.docs[0].id,
        result: existing.docs[0].result,
        saved: true,
      })
    const attempt = await payload.create({
      collection: 'quiz-attempts',
      user,
      overrideAccess: false,
      context: { quizSubmission: true },
      data: { ...input, owner: user.id },
    })
    return Response.json({ id: attempt.id, result: attempt.result, saved: true })
  } catch (error) {
    const message = error instanceof Error ? error.message : ''
    const safe =
      /^(Dữ liệu bài làm|Thông tin bài làm|Câu trả lời|Bộ câu hỏi|Không thể truy cập)/.test(message)
        ? message
        : 'Chưa nộp được bài. Vui lòng thử lại; câu trả lời của bạn vẫn được giữ nguyên.'
    return Response.json({ error: safe }, { status: 400 })
  }
}

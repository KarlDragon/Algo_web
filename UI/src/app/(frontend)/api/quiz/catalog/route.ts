import { getPayloadClient, findBySlug } from '@/lib/payload'
import type { QuizColor, QuizQuestionView, QuizTopicView } from '@/lib/quiz'

// Static application shells load a fresh question bank for each practice session.
// Answers are field-access protected and are never included in this public response.
export async function GET(request: Request) {
  try {
    const payload = await getPayloadClient()
    const slug = new URL(request.url).searchParams.get('topic')
    if (slug) {
      const topic = await findBySlug('quiz-topics', slug, { depth: 0 })
      if (!topic) return Response.json({ error: 'Không tìm thấy chủ đề này.' }, { status: 404 })
      const { docs } = await payload.find({
        collection: 'quiz-questions',
        overrideAccess: false,
        depth: 0,
        limit: 200,
        sort: 'code',
        where: { topic: { equals: topic.id } },
      })
      const questions: QuizQuestionView[] = docs.map((q) => ({
        id: q.id,
        code: q.code,
        prompt: q.prompt,
        level: q.level,
        options: (q.options ?? []).map((o) => o.text),
      }))
      return Response.json(
        {
          topic: {
            id: topic.id,
            slug: topic.slug,
            title: topic.title,
            description: topic.description,
          },
          questions,
        },
        { headers: { 'Cache-Control': 'no-store' } },
      )
    }
    const [{ docs: topics }, { docs: questions }] = await Promise.all([
      payload.find({
        collection: 'quiz-topics',
        overrideAccess: false,
        depth: 0,
        sort: 'order',
        limit: 100,
      }),
      payload.find({
        collection: 'quiz-questions',
        overrideAccess: false,
        depth: 0,
        limit: 2000,
        select: { topic: true, level: true },
      }),
    ])
    const result: QuizTopicView[] = topics.map((t) => {
      const list = questions.filter(
        (q) => (typeof q.topic === 'object' ? q.topic?.id : q.topic) === t.id,
      )
      return {
        id: t.id,
        slug: t.slug,
        title: t.title,
        description: t.description,
        category: t.category,
        color: t.color as QuizColor,
        icon: t.icon,
        order: t.order ?? 0,
        questionCount: list.length,
        levels: {
          easy: list.filter((q) => q.level === 'easy').length,
          medium: list.filter((q) => q.level === 'medium').length,
          hard: list.filter((q) => q.level === 'hard').length,
        },
      }
    })
    return Response.json({ topics: result }, { headers: { 'Cache-Control': 'no-store' } })
  } catch {
    return Response.json(
      { error: 'Chưa tải được ngân hàng câu hỏi. Vui lòng thử lại.' },
      { status: 500 },
    )
  }
}

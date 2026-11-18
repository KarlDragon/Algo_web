import { QuizRunner } from '@/components/quiz-runner'
import { getPayloadClient } from '@/lib/payload'

// These are static application shells. Question content is read fresh from
// Payload by the practice API, never embedded with answer keys in the HTML.
export const dynamicParams = false
export async function generateStaticParams() {
  const payload = await getPayloadClient()
  const { docs } = await payload.find({
    collection: 'quiz-topics',
    overrideAccess: false,
    depth: 0,
    limit: 100,
    select: { slug: true },
  })
  return docs.map((topic) => ({ slug: topic.slug }))
}
export default async function QuizTopicPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  return <QuizRunner key={slug} slug={slug} />
}

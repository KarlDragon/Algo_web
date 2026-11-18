import { notFound } from 'next/navigation'
import { algorithms } from '@/lib/algorithms'
import { Simulator } from '@/components/simulator'

export const dynamicParams = false
export function generateStaticParams() {
  return algorithms.map((a) => ({ slug: a.slug }))
}
export default async function AlgorithmPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const algorithm = algorithms.find((a) => a.slug === slug)
  if (!algorithm) notFound()
  return <Simulator key={slug} algorithm={algorithm} />
}

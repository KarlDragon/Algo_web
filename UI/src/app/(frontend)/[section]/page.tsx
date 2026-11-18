import { notFound } from 'next/navigation'
import { AlgorithmLibrary } from '@/components/dashboard'
import { ProfilePage, HistoryPage, SettingsPage } from '@/components/account-pages'
import { ComparePage } from '@/components/compare'
import { AboutPage } from '@/components/about'
import { categories, type Category } from '@/lib/algorithms'

const sections = [
  'sorting',
  'searching',
  'graphs',
  'dynamic',
  'algorithms',
  'history',
  'compare',
  'profile',
  'settings',
  'about',
]
export const dynamicParams = false
export function generateStaticParams() {
  return sections.map((section) => ({ section }))
}
export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params
  if (categories.some((c) => c.id === section))
    return <AlgorithmLibrary category={section as Category} />
  switch (section) {
    case 'algorithms':
      return <AlgorithmLibrary />
    case 'history':
      return <HistoryPage />
    case 'compare':
      return <ComparePage />
    case 'profile':
      return <ProfilePage />
    case 'settings':
      return <SettingsPage />
    case 'about':
      return <AboutPage />
    default:
      notFound()
  }
}

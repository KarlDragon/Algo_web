import type { User } from './auth'

export type UserProfile = User & {
  full_name: string | null
  avatar_url: string | null
  created_at: string
}

export type PageMeta = {
  page: number
  page_size: number
  total: number
}

export type Page<T> = {
  data: T[]
  meta: PageMeta
}

export type Category = {
  id: number
  name: string
  slug: string
  description: string | null
  algorithm_count: number | null
}

export type AlgorithmSummary = {
  id: number
  slug: string
  name: string
  summary: string
  category: string
  category_id: number
  difficulty: 'EASY' | 'MEDIUM' | 'HARD'
  avg_rating: number
  rating_count: number
  has_simulation: boolean
}

export type AlgorithmDetail = AlgorithmSummary & {
  theory: string
  pseudocode: string
  code_samples: Array<{ id: number; language: string; code: string }>
  complexity: {
    time_best: string
    time_average: string
    time_worst: string
    space: string
  }
  tags: Array<{ id: number; name: string; slug: string }>
  examples: Array<{
    id: number
    title: string
    input_data: string
    expected_output: string
    explanation: string
    sort_order: number
  }>
  diagrams: Array<{
    id: number
    title: string
    diagram_type: string
    source_text: string | null
    image_url: string | null
    sort_order: number
  }>
  visualization_config: { renderer_key: string; config_json: string } | null
  comment_count: number
  created_at: string
  updated_at: string
}

export type HomeData = {
  intro: { title: string; description: string }
  banners: Array<{
    id: number
    title: string
    image_url: string
    link_url: string
    sort_order: number
    is_active: boolean
  }>
  featured_algorithms: AlgorithmSummary[]
  categories: Category[]
  stats: { algorithms: number; users: number }
}

export type Comment = {
  id: number
  content: string
  author: { id: number; username: string; avatar_url: string | null }
  algorithm_id: number
  parent_id: number | null
  reply_count: number
  created_at: string
  updated_at: string
  is_mine: boolean
}

export type Rating = {
  avg_rating: number
  rating_count: number
  my_score: number | null
  distribution: Record<string, number>
}

export type LearningProgress = {
  algorithm_id: number
  status: 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED'
  progress_percent: number
  last_viewed_at: string | null
  completed_at: string | null
}

export type AuthTokens = {
  access_token: string
  refresh_token: string
  expires_in: number
  token_type: string
}

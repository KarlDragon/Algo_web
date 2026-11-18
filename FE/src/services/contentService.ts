import type {
  AlgorithmDetail,
  AlgorithmSummary,
  Category,
  Comment,
  HomeData,
  LearningProgress,
  Page,
  Rating,
  UserProfile,
} from '../models/api'
import { apiRequest } from './apiClient'

type ListOptions = {
  page?: number
  pageSize?: number
  categoryId?: number
  difficulty?: AlgorithmSummary['difficulty']
  sort?: 'name' | 'rating' | 'newest'
}

function queryString(values: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined) query.set(key, String(value))
  })
  const serialized = query.toString()
  return serialized ? `?${serialized}` : ''
}

export const getMe = () => apiRequest<UserProfile>('/users/me')
export const getHome = () => apiRequest<HomeData>('/home')
export const getCategories = () => apiRequest<Category[]>('/categories')
export const getAlgorithm = (slug: string) =>
  apiRequest<AlgorithmDetail>(`/algorithms/${encodeURIComponent(slug)}`)

export function getAlgorithms(options: ListOptions = {}) {
  return apiRequest<Page<AlgorithmSummary>>(
    `/algorithms${queryString({
      page: options.page ?? 1,
      page_size: options.pageSize ?? 20,
      category_id: options.categoryId,
      difficulty: options.difficulty,
      sort: options.sort ?? 'name',
    })}`,
  )
}

export function searchAlgorithms(q: string, page = 1) {
  return apiRequest<Page<AlgorithmSummary & { matched_in: string }>>(
    `/search${queryString({ q, page, page_size: 20 })}`,
  )
}

export function getSuggestions(q: string) {
  return apiRequest<Array<{ slug: string; name: string }>>(
    `/search/suggestions${queryString({ q, limit: 6 })}`,
  )
}

export const getFavorites = (page = 1) =>
  apiRequest<Page<AlgorithmSummary>>(
    `/users/me/favorites${queryString({ page, page_size: 100 })}`,
  )

export const getProgress = (id: number) =>
  apiRequest<LearningProgress>(`/algorithms/${id}/progress`)

export const updateProgress = (
  id: number,
  status: LearningProgress['status'],
  progress_percent: number,
) =>
  apiRequest<LearningProgress>(`/algorithms/${id}/progress`, {
    method: 'PUT',
    body: JSON.stringify({ status, progress_percent }),
  })

export const saveFavorite = (id: number) =>
  apiRequest<{ message: string }>(`/algorithms/${id}/favorite`, { method: 'POST' })

export const removeFavorite = (id: number) =>
  apiRequest<void>(`/algorithms/${id}/favorite`, { method: 'DELETE' })

export const getComments = (id: number) =>
  apiRequest<Page<Comment>>(`/algorithms/${id}/comments?page=1&page_size=20&sort=newest`)

export const addComment = (id: number, content: string) =>
  apiRequest<Comment>(`/algorithms/${id}/comments`, {
    method: 'POST',
    body: JSON.stringify({ content, parent_id: null }),
  })

export const getRating = (id: number) =>
  apiRequest<Rating>(`/algorithms/${id}/rating`)

export const setRating = (id: number, score: number) =>
  apiRequest<Rating>(`/algorithms/${id}/rating`, {
    method: 'PUT',
    body: JSON.stringify({ score }),
  })

export const updateProfile = (full_name: string) =>
  apiRequest<UserProfile>('/users/me', {
    method: 'PATCH',
    body: JSON.stringify({ full_name }),
  })

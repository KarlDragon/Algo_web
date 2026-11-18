import { useEffect, useMemo, useState, type FormEvent } from 'react'
import type { UserProfile } from '../models/api'
import type {
  AlgorithmDetail as AlgorithmDetailData,
  AlgorithmSummary,
  Category,
  HomeData,
  Page,
} from '../models/api'
import {
  getAlgorithm,
  getAlgorithms,
  getCategories,
  getFavorites,
  getHome,
  getProgress,
  getSuggestions,
  searchAlgorithms,
  updateProfile,
  updateProgress,
} from '../services/contentService'
import {
  ApiError,
  clearSession,
  getStoredRefreshToken,
} from '../services/apiClient'
import { apiRequest } from '../services/apiClient'
import AlgorithmDetail from './AlgorithmDetail'

type Route =
  | { page: 'home' }
  | { page: 'algorithms' }
  | { page: 'search'; query: string }
  | { page: 'favorites' }
  | { page: 'profile' }
  | { page: 'algorithm'; slug: string }
  | { page: 'category'; slug: string }

function resolveRoute(pathname: string, search: string, categories: Category[]): Route {
  const parts = pathname.split('/').filter(Boolean)
  if (parts.length === 0) return { page: 'home' }
  if (parts[0] === 'algorithm' && parts[1]) {
    return { page: 'algorithm', slug: decodeURIComponent(parts[1]) }
  }
  if (parts[0] === 'algorithms') {
    return parts[1]
      ? { page: 'algorithm', slug: decodeURIComponent(parts[1]) }
      : { page: 'algorithms' }
  }
  if (parts[0] === 'search') {
    return { page: 'search', query: new URLSearchParams(search).get('q') ?? '' }
  }
  if (parts[0] === 'favorites') return { page: 'favorites' }
  if (parts[0] === 'profile') return { page: 'profile' }
  const category = categories.find((item) => item.slug === parts[0])
  if (category) return { page: 'category', slug: category.slug }
  return { page: 'home' }
}

function difficultyLabel(difficulty: AlgorithmSummary['difficulty']): string {
  return { EASY: 'Dễ', MEDIUM: 'Trung bình', HARD: 'Nâng cao' }[difficulty]
}

function messageFrom(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) {
    return 'Không thể kết nối máy chủ. Hãy kiểm tra backend đang chạy rồi thử lại.'
  }
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

function AlgorithmCard({ item }: { item: AlgorithmSummary }) {
  return (
    <article className="algorithm-card">
      <div className="algorithm-card-top">
        <span className="category-chip">{item.category}</span>
        <span className={`difficulty difficulty-${item.difficulty.toLowerCase()}`}>
          {difficultyLabel(item.difficulty)}
        </span>
      </div>
      <h3>{item.name}</h3>
      <p>{item.summary}</p>
      <div className="algorithm-card-meta">
        <span>{item.avg_rating.toFixed(1)} ★</span>
        <span>{item.rating_count} đánh giá</span>
        {item.has_simulation && <span>Mô phỏng</span>}
      </div>
      <a className="card-link" href={`/algorithm/${encodeURIComponent(item.slug)}`}>
        Khám phá thuật toán <span aria-hidden="true">→</span>
      </a>
    </article>
  )
}

function AlgorithmGrid({ items }: { items: AlgorithmSummary[] }) {
  if (!items.length) {
    return <p className="empty-state">Chưa có thuật toán phù hợp.</p>
  }
  return (
    <div className="algorithm-grid">
      {items.map((item) => (
        <AlgorithmCard item={item} key={item.id} />
      ))}
    </div>
  )
}

function LoadingState() {
  return (
    <div className="loading-state" role="status">
      <span className="loading-spinner" />
      Đang tải dữ liệu…
    </div>
  )
}

function SearchBox() {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<Array<{ slug: string; name: string }>>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const trimmed = query.trim()
    if (trimmed.length < 1) {
      setSuggestions([])
      return
    }
    let active = true
    const timeout = window.setTimeout(() => {
      getSuggestions(trimmed)
        .then((items) => {
          if (active) setSuggestions(items)
        })
        .catch(() => {
          if (active) setSuggestions([])
        })
    }, 250)
    return () => {
      active = false
      window.clearTimeout(timeout)
    }
  }, [query])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (query.trim()) {
      window.location.href = `/search?q=${encodeURIComponent(query.trim())}`
    }
  }

  return (
    <form className="search-box" onSubmit={submit} role="search">
      <span aria-hidden="true" className="search-icon">
        ⌕
      </span>
      <input
        aria-label="Tìm thuật toán"
        autoComplete="off"
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => setOpen(true)}
        placeholder="Tìm kiếm thuật toán…"
        value={query}
      />
      <kbd>⌘ K</kbd>
      {open && suggestions.length > 0 && (
        <div className="suggestion-menu">
          {suggestions.map((item) => (
            <a href={`/algorithm/${encodeURIComponent(item.slug)}`} key={item.slug}>
              {item.name}
              <span aria-hidden="true">↗</span>
            </a>
          ))}
          {query.trim() && (
            <button type="submit">Xem tất cả kết quả cho “{query.trim()}”</button>
          )}
        </div>
      )}
    </form>
  )
}

function HomePage({ data }: { data: HomeData }) {
  return (
    <div className="page-enter">
      <section className="hero-panel">
        <div className="eyebrow"><span /> SẴN SÀNG CHO MỘT ĐIỀU MỚI?</div>
        <h2>{data.intro.title}</h2>
        <p>{data.intro.description}</p>
        <div className="hero-actions">
          <a className="primary-button" href="/algorithms">Bắt đầu học ngay <span>→</span></a>
          <a className="quiet-link" href="/favorites">Xem danh sách yêu thích</a>
        </div>
        <div aria-hidden="true" className="hero-orbit">
          <span>O(n log n)</span><i /><b /><em />
        </div>
      </section>
      <section className="stats-grid" aria-label="Thống kê">
        <div className="stat-card"><strong>{data.stats.algorithms}</strong><span>Thuật toán</span><small>Kiến thức từ cơ bản đến nâng cao</small></div>
        <div className="stat-card"><strong>{data.categories.length}</strong><span>Danh mục</span><small>Khám phá nhiều chủ đề</small></div>
        <div className="stat-card"><strong>{data.stats.users}</strong><span>Người học</span><small>Cùng học và chia sẻ kiến thức</small></div>
        <div className="stat-card"><strong>{data.featured_algorithms.length}</strong><span>Nổi bật</span><small>Được cộng đồng quan tâm</small></div>
      </section>
      {data.banners.length > 0 && (
        <section className="banner-strip" aria-label="Thông tin nổi bật">
          {data.banners.map((banner) => (
            <a href={banner.link_url} key={banner.id}>
              <span>{banner.title}</span><span aria-hidden="true">↗</span>
            </a>
          ))}
        </section>
      )}
      <section className="workspace-section">
        <div className="section-heading">
          <div><h2>Chọn một chủ đề để khám phá</h2><p>Bắt đầu từ danh mục phù hợp với hành trình của bạn.</p></div>
          <a href="/algorithms">Tất cả thuật toán →</a>
        </div>
        <div className="category-grid">
          {data.categories.map((category, index) => (
            <a className={`category-card category-card-${index % 4}`} href={`/${encodeURIComponent(category.slug)}`} key={category.id}>
              <span className="category-symbol">{['↗', '⌕', '⌘', '◈'][index % 4]}</span>
              <h3>{category.name}</h3>
              <p>{category.description ?? 'Khám phá các thuật toán trong danh mục này.'}</p>
              <small>{category.algorithm_count ?? 0} thuật toán <span>→</span></small>
            </a>
          ))}
        </div>
      </section>
      <section className="workspace-section">
        <div className="section-heading">
          <div><h2>Thuật toán nổi bật</h2><p>Khám phá các nội dung đang được quan tâm.</p></div>
          <a href="/algorithms">Xem thư viện →</a>
        </div>
        <AlgorithmGrid items={data.featured_algorithms} />
      </section>
    </div>
  )
}

function ProfilePage({
  user,
  onProfileChange,
}: {
  user: UserProfile
  onProfileChange: (user: UserProfile) => void
}) {
  const [name, setName] = useState(user.full_name ?? '')
  const [notice, setNotice] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setNotice('')
    try {
      const updated = await updateProfile(name.trim())
      onProfileChange(updated)
      setNotice('Đã cập nhật hồ sơ.')
    } catch (error) {
      setNotice(messageFrom(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="content-panel profile-panel">
      <div className="section-heading"><div><h2>Hồ sơ cá nhân</h2><p>Thông tin tài khoản AlgoVisual của bạn.</p></div></div>
      <div className="profile-identity">
        <span className="avatar-large">{(user.full_name || user.username).slice(0, 1).toUpperCase()}</span>
        <div><strong>{user.full_name || user.username}</strong><span>{user.role ?? 'USER'}</span></div>
      </div>
      <form className="profile-form" onSubmit={submit}>
        <label>Tên hiển thị<input maxLength={100} onChange={(event) => setName(event.target.value)} value={name} /></label>
        <label>Tên đăng nhập<input readOnly value={user.username} /></label>
        <label>Email<input readOnly value={user.email} /></label>
        <button className="primary-button" disabled={saving} type="submit">{saving ? 'Đang lưu…' : 'Lưu thay đổi'}</button>
      </form>
      {notice && <p className="inline-notice" role="status">{notice}</p>}
    </section>
  )
}

type WorkspaceProps = {
  user: UserProfile
  onLogout: (error?: string) => Promise<void>
  onProfileChange: (user: UserProfile) => void
}

export default function LearningWorkspace({ user, onLogout, onProfileChange }: WorkspaceProps) {
  const [categories, setCategories] = useState<Category[]>([])
  const route = useMemo(
    () => resolveRoute(window.location.pathname, window.location.search, categories),
    [categories],
  )
  const routeSlug = route.page === 'algorithm' || route.page === 'category' ? route.slug : ''
  const routeQuery = route.page === 'search' ? route.query : ''
  const [home, setHome] = useState<HomeData | null>(null)
  const [list, setList] = useState<Page<AlgorithmSummary> | null>(null)
  const [detail, setDetail] = useState<AlgorithmDetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [difficulty, setDifficulty] = useState<'' | AlgorithmSummary['difficulty']>('')
  const [sort, setSort] = useState<'name' | 'rating' | 'newest'>('rating')
  const [mobileNav, setMobileNav] = useState(false)
  const [accountMenu, setAccountMenu] = useState(false)
  const [favorites, setFavorites] = useState<Set<string>>(new Set())
  const title =
    route.page === 'home' ? 'Trang chủ' :
    route.page === 'algorithm' ? (detail?.name ?? 'Thuật toán') :
    route.page === 'category' ? (categories.find((item) => item.slug === route.slug)?.name ?? 'Danh mục') :
    route.page === 'profile' ? 'Hồ sơ cá nhân' :
    route.page === 'favorites' ? 'Thuật toán yêu thích' :
    route.page === 'search' ? 'Kết quả tìm kiếm' : 'Thư viện thuật toán'

  useEffect(() => {
    let active = true
    getCategories()
      .then((items) => { if (active) setCategories(items) })
      .catch((cause: unknown) => { if (active) setError(messageFrom(cause)) })
    getFavorites()
      .then((result) => { if (active) setFavorites(new Set(result.data.map((item) => item.slug))) })
      .catch(() => {
        if (active) setFavorites(new Set())
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    setHome(null)
    setList(null)
    setDetail(null)
    const load = async () => {
      try {
        if (route.page === 'home') {
          const result = await getHome()
          if (active) setHome(result)
        } else if (route.page === 'algorithm') {
          const result = await getAlgorithm(routeSlug)
          if (active) setDetail(result)
        } else if (route.page === 'favorites') {
          const result = await getFavorites()
          if (active) setList(result)
        } else if (route.page === 'search') {
          if (!routeQuery.trim()) {
            if (active) setList({ data: [], meta: { page: 1, page_size: 20, total: 0 } })
          } else {
            const result = await searchAlgorithms(routeQuery)
            if (active) setList(result)
          }
        } else if (route.page === 'profile') {
          if (active) setList(null)
        } else {
          const category = route.page === 'category'
            ? categories.find((item) => item.slug === routeSlug)
            : undefined
          const result = await getAlgorithms({
            categoryId: category?.id,
            difficulty: difficulty || undefined,
            sort,
          })
          if (active) setList(result)
        }
      } catch (cause) {
        if (active) setError(messageFrom(cause))
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => { active = false }
  }, [route.page, routeSlug, routeQuery, categories, difficulty, sort])

  useEffect(() => {
    if (!detail) return
    void getProgress(detail.id)
      .then((progress) => {
        if (progress.status === 'NOT_STARTED') {
          return updateProgress(detail.id, 'IN_PROGRESS', 10)
        }
        return undefined
      })
      .catch((cause: unknown) => setError(messageFrom(cause)))
  }, [detail])

  async function toggleFavorite(algorithm: AlgorithmDetailData) {
    const isSaved = favorites.has(algorithm.slug)
    try {
      if (isSaved) {
        await apiRequest<void>(`/algorithms/${algorithm.id}/favorite`, { method: 'DELETE' })
        setFavorites((previous) => {
          const next = new Set(previous)
          next.delete(algorithm.slug)
          return next
        })
      } else {
        await apiRequest(`/algorithms/${algorithm.id}/favorite`, { method: 'POST' })
        setFavorites((previous) => new Set(previous).add(algorithm.slug))
      }
    } catch (cause) {
      setError(messageFrom(cause))
    }
  }

  async function logout() {
    try {
      await apiRequest('/users/me')
      const refreshToken = getStoredRefreshToken()
      if (refreshToken) {
        await apiRequest('/auth/logout', {
          method: 'POST',
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
      }
    } catch (cause) {
      await onLogout(messageFrom(cause))
      clearSession()
      return
    } finally {
      clearSession()
    }
    await onLogout()
  }

  const isLibrary = route.page === 'algorithms' || route.page === 'category'
  const category = route.page === 'category'
    ? categories.find((item) => item.slug === route.slug)
    : undefined

  return (
    <div className="workspace">
      {mobileNav && <button className="mobile-backdrop" onClick={() => setMobileNav(false)} aria-label="Đóng điều hướng" />}
      <aside className={`sidebar${mobileNav ? ' sidebar-open' : ''}`}>
        <a className="brand" href="/">
          <span className="brand-mark">A</span>
          <span>Algo<span>Visual</span></span>
        </a>
        <p className="nav-caption">KHÔNG GIAN HỌC TẬP</p>
        <nav className="side-nav" aria-label="Điều hướng chính">
          <a className={route.page === 'home' ? 'nav-active' : ''} href="/">⌂ <span>Trang chủ</span></a>
          <a className={isLibrary ? 'nav-active' : ''} href="/algorithms">▦ <span>Thư viện thuật toán</span></a>
          {categories.map((item) => (
            <a className={route.page === 'category' && route.slug === item.slug ? 'nav-active nav-child-active' : 'nav-child'} href={`/${encodeURIComponent(item.slug)}`} key={item.id}>
              <span className="nav-dot" /> <span>{item.name}</span>
            </a>
          ))}
          <a className={route.page === 'favorites' ? 'nav-active' : ''} href="/favorites">☆ <span>Yêu thích</span></a>
          <a className={route.page === 'profile' ? 'nav-active' : ''} href="/profile">◉ <span>Hồ sơ cá nhân</span></a>
        </nav>
        <div className="sidebar-bottom">
          <div className="learning-tip"><span>✦</span><strong>Mỗi ngày, một bước tiến</strong><p>Một thuật toán nhỏ hôm nay. Một bước tiến lớn ngày mai.</p><a href="/algorithms">Tiếp tục khám phá →</a></div>
          <div className="sidebar-user"><span className="avatar">{(user.full_name || user.username).slice(0, 1).toUpperCase()}</span><div><strong>{user.full_name || user.username}</strong><small>Người học AlgoVisual</small></div></div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <div className="topbar-title">
            <button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="Mở điều hướng">☰</button>
            <h1>{title}</h1><span className="workspace-badge">Learning workspace</span>
          </div>
          <div className="topbar-actions"><SearchBox />
            <div className="account-wrap">
              <button className="account-button" onClick={() => setAccountMenu((value) => !value)} aria-expanded={accountMenu} aria-label="Tài khoản"><span className="avatar">{(user.full_name || user.username).slice(0, 1).toUpperCase()}</span><span className="account-label">{user.full_name || user.username}</span><span>⌄</span></button>
              {accountMenu && <div className="account-menu"><a href="/profile">Hồ sơ cá nhân</a><button onClick={() => void logout()}>Đăng xuất</button></div>}
            </div>
          </div>
        </header>
        <main className="workspace-content">
          {error && <div className="notice-error" role="alert">{error}<button onClick={() => setError('')} aria-label="Đóng">×</button></div>}
          {loading && <LoadingState />}
          {!loading && route.page === 'home' && home && <HomePage data={home} />}
          {!loading && route.page === 'algorithm' && detail && (
            <AlgorithmDetail
              algorithm={detail}
              isFavorite={favorites.has(detail.slug)}
              onFavorite={() => void toggleFavorite(detail)}
            />
          )}
          {!loading && route.page === 'favorites' && (
            <section className="workspace-section"><div className="section-heading"><div><h2>Đã lưu để học sau</h2><p>{list?.meta.total ?? 0} thuật toán yêu thích</p></div></div><AlgorithmGrid items={list?.data ?? []} /></section>
          )}
          {!loading && (isLibrary || route.page === 'search') && (
            <section className="workspace-section">
              <div className="library-intro"><span className="eyebrow">THƯ VIỆN THUẬT TOÁN</span><h2>{route.page === 'search' ? `Kết quả cho “${route.query}”` : category?.name ?? 'Một thư viện. Vô vàn khám phá.'}</h2><p>{category?.description ?? 'Tìm hiểu lý thuyết, độ phức tạp và mô phỏng từng bước.'}</p></div>
              {route.page !== 'search' && <div className="filter-row">
                <label>Độ khó<select value={difficulty} onChange={(event) => setDifficulty(event.target.value as '' | AlgorithmSummary['difficulty'])}><option value="">Tất cả</option><option value="EASY">Dễ</option><option value="MEDIUM">Trung bình</option><option value="HARD">Nâng cao</option></select></label>
                <label>Sắp xếp<select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="rating">Được đánh giá cao</option><option value="name">Tên A–Z</option><option value="newest">Mới nhất</option></select></label>
              </div>}
              <p className="result-count">{list?.meta.total ?? 0} thuật toán</p>
              <AlgorithmGrid items={list?.data ?? []} />
            </section>
          )}
          {!loading && route.page === 'profile' && <ProfilePage user={user} onProfileChange={onProfileChange} />}
        </main>
        <footer className="workspace-footer"><span>© {new Date().getFullYear()} AlgoVisual</span><span>Học thuật toán theo cách của bạn.</span></footer>
      </div>
    </div>
  )
}

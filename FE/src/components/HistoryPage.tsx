import { useEffect, useState } from 'react'
import type { HistoryItem, PageMeta } from '../models/api'
import { ApiError } from '../services/apiClient'
import { getHistory } from '../services/contentService'

function messageFrom(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) return 'Không thể kết nối máy chủ.'
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi.'
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Không rõ thời gian'
    : new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

type StatusFilter = '' | 'IN_PROGRESS' | 'COMPLETED'

export default function HistoryPage() {
  const [status, setStatus] = useState<StatusFilter>('')
  const [items, setItems] = useState<HistoryItem[]>([])
  const [meta, setMeta] = useState<PageMeta | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    getHistory({ page: 1, pageSize: 20, status: status || undefined })
      .then((result) => {
        if (!active) return
        setItems(result.data)
        setMeta(result.meta)
      })
      .catch((cause: unknown) => {
        if (active) setError(messageFrom(cause))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [status])

  async function loadMore() {
    if (!meta || loadingMore || items.length >= meta.total) return
    setLoadingMore(true)
    setError('')
    try {
      const result = await getHistory({
        page: meta.page + 1,
        pageSize: meta.page_size,
        status: status || undefined,
      })
      setItems((previous) => [...previous, ...result.data])
      setMeta(result.meta)
    } catch (cause) {
      setError(messageFrom(cause))
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <section className="workspace-section page-enter">
      <div className="section-heading">
        <div>
          <h2>Lịch sử học tập</h2>
          <p>Theo dõi tiến độ và tiếp tục từ nơi bạn đã dừng lại.</p>
        </div>
      </div>
      <div className="history-filter" aria-label="Lọc lịch sử học tập">
        {([
          ['', 'Tất cả'],
          ['IN_PROGRESS', 'Đang học'],
          ['COMPLETED', 'Đã hoàn thành'],
        ] as const).map(([value, label]) => (
          <button
            aria-pressed={status === value}
            className={status === value ? 'history-filter-active' : ''}
            key={value || 'all'}
            onClick={() => setStatus(value)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p className="notice-error" role="alert">{error}</p>}
      {loading && <div className="loading-state" role="status"><span className="loading-spinner" />Đang tải lịch sử…</div>}
      {!loading && !error && items.length === 0 && (
        <div className="content-panel history-empty">
          <h3>Chưa có lịch sử học tập</h3>
          <p>Khi bạn mở một thuật toán, nội dung đó sẽ xuất hiện tại đây.</p>
          <a className="primary-button" href="/algorithms">Khám phá thuật toán</a>
        </div>
      )}
      {!loading && items.length > 0 && (
        <div className="history-list">
          {items.map((item) => (
            <article className="history-card content-panel" key={item.algorithm.id}>
              <div className="history-card-main">
                <div>
                  <span className="category-chip">{item.algorithm.category}</span>
                  <h3><a href={`/algorithm/${encodeURIComponent(item.algorithm.slug)}`}>{item.algorithm.name}</a></h3>
                  <p>{item.algorithm.summary}</p>
                  <small>Lần xem gần nhất: {formatDate(item.last_viewed_at)}</small>
                </div>
                <div className="history-progress-label">
                  <span>{item.status === 'COMPLETED' ? 'Đã hoàn thành' : 'Đang học'}</span>
                  <strong>{item.progress_percent}%</strong>
                </div>
              </div>
              <div
                aria-label={`Tiến độ ${item.progress_percent}%`}
                aria-valuemax={100}
                aria-valuemin={0}
                aria-valuenow={item.progress_percent}
                className="history-progress"
                role="progressbar"
              >
                <span style={{ width: `${item.progress_percent}%` }} />
              </div>
              <a className="history-continue" href={`/algorithm/${encodeURIComponent(item.algorithm.slug)}`}>Tiếp tục học <span aria-hidden="true">→</span></a>
            </article>
          ))}
          {meta && items.length < meta.total && (
            <button className="secondary-button history-load-more" disabled={loadingMore} onClick={() => void loadMore()} type="button">
              {loadingMore ? 'Đang tải…' : 'Tải thêm'}
            </button>
          )}
        </div>
      )}
    </section>
  )
}

import { useEffect, useState, type FormEvent } from 'react'
import type { AlgorithmDetail as AlgorithmData, Comment, Rating } from '../models/api'
import {
  addComment,
  getComments,
  getRating,
  setRating,
  updateProgress,
} from '../services/contentService'
import { ApiError } from '../services/apiClient'
import AlgorithmSimulator from './AlgorithmSimulator'

type Props = {
  algorithm: AlgorithmData
  isFavorite: boolean
  onFavorite: () => void
}

function messageFrom(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) return 'Không thể kết nối máy chủ.'
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi.'
}

function humanDate(value: string): string {
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' }).format(new Date(value))
}

export default function AlgorithmDetail({ algorithm, isFavorite, onFavorite }: Props) {
  const [comments, setComments] = useState<Comment[]>([])
  const [rating, setRatingData] = useState<Rating | null>(null)
  const [commentText, setCommentText] = useState('')
  const [commentBusy, setCommentBusy] = useState(false)
  const [ratingBusy, setRatingBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [tab, setTab] = useState<'overview' | 'code' | 'pseudocode'>('overview')

  useEffect(() => {
    let active = true
    getComments(algorithm.id)
      .then((result) => { if (active) setComments(result.data) })
      .catch((error: unknown) => { if (active) setNotice(messageFrom(error)) })
    getRating(algorithm.id)
      .then((result) => { if (active) setRatingData(result) })
      .catch((error: unknown) => { if (active) setNotice(messageFrom(error)) })
    return () => { active = false }
  }, [algorithm.id])

  async function submitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = commentText.trim()
    if (!content) return
    setCommentBusy(true)
    setNotice('')
    try {
      const created = await addComment(algorithm.id, content)
      setComments((previous) => [created, ...previous])
      setCommentText('')
    } catch (error) {
      setNotice(messageFrom(error))
    } finally {
      setCommentBusy(false)
    }
  }

  async function submitRating(score: number) {
    setRatingBusy(true)
    setNotice('')
    try {
      setRatingData(await setRating(algorithm.id, score))
    } catch (error) {
      setNotice(messageFrom(error))
    } finally {
      setRatingBusy(false)
    }
  }

  async function markComplete() {
    setNotice('')
    try {
      await updateProgress(algorithm.id, 'COMPLETED', 100)
      setNotice('Đã ghi nhận hoàn thành thuật toán.')
    } catch (error) {
      setNotice(messageFrom(error))
    }
  }

  return (
    <div className="page-enter algorithm-detail">
      <a className="back-link" href="/algorithms">← Quay lại thư viện</a>
      <section className="detail-hero">
        <div>
          <div className="eyebrow">{algorithm.category.toUpperCase()} <span>•</span> {algorithm.slug}</div>
          <h2>{algorithm.name}</h2>
          <p>{algorithm.summary}</p>
          <div className="detail-meta">
            <span className={`difficulty difficulty-${algorithm.difficulty.toLowerCase()}`}>{algorithm.difficulty}</span>
            <span>{algorithm.avg_rating.toFixed(1)} ★ ({algorithm.rating_count} đánh giá)</span>
            <span>{algorithm.comment_count} bình luận</span>
          </div>
        </div>
        <button className={`favorite-button${isFavorite ? ' is-favorite' : ''}`} onClick={onFavorite}>
          {isFavorite ? '★ Đã lưu' : '☆ Lưu yêu thích'}
        </button>
      </section>

      {notice && <p className="inline-notice" role="status">{notice}</p>}

      {algorithm.has_simulation && <AlgorithmSimulator algorithm={algorithm} />}

      <section className="complexity-grid" aria-label="Độ phức tạp">
        <div><small>Thời gian tốt nhất</small><strong>{algorithm.complexity.time_best}</strong></div>
        <div><small>Thời gian trung bình</small><strong>{algorithm.complexity.time_average}</strong></div>
        <div><small>Thời gian xấu nhất</small><strong>{algorithm.complexity.time_worst}</strong></div>
        <div><small>Bộ nhớ</small><strong>{algorithm.complexity.space}</strong></div>
      </section>

      <div className="detail-tabs" role="tablist" aria-label="Nội dung thuật toán">
        <button aria-selected={tab === 'overview'} onClick={() => setTab('overview')} role="tab">Tổng quan</button>
        <button aria-selected={tab === 'pseudocode'} onClick={() => setTab('pseudocode')} role="tab">Mã giả</button>
        <button aria-selected={tab === 'code'} onClick={() => setTab('code')} role="tab">Mã nguồn</button>
      </div>
      <section className="content-panel detail-content">
        {tab === 'overview' && (
          <>
            <h3>Lý thuyết</h3>
            <p className="prose-text">{algorithm.theory}</p>
            {algorithm.tags.length > 0 && <div className="tag-row">{algorithm.tags.map((tag) => <span key={tag.id}>{tag.name}</span>)}</div>}
            {algorithm.examples.map((example) => (
              <article className="example-card" key={example.id}>
                <h4>{example.title}</h4>
                <p>{example.explanation}</p>
                <div className="example-values"><span>Đầu vào <code>{example.input_data}</code></span><span>Kết quả <code>{example.expected_output}</code></span></div>
              </article>
            ))}
            <button className="secondary-button" onClick={() => void markComplete()}>Đánh dấu đã hoàn thành</button>
          </>
        )}
        {tab === 'pseudocode' && <><h3>Mã giả</h3><pre className="code-block"><code>{algorithm.pseudocode}</code></pre></>}
        {tab === 'code' && (
          <>
            <h3>Mã nguồn tham khảo</h3>
            {algorithm.code_samples.length ? algorithm.code_samples.map((sample) => (
              <article className="sample-code" key={sample.id}><div>{sample.language}</div><pre className="code-block"><code>{sample.code}</code></pre></article>
            )) : <p className="empty-state">Chưa có mã nguồn tham khảo.</p>}
          </>
        )}
      </section>

      <section className="interaction-grid">
        <div className="content-panel rating-panel">
          <div className="section-heading"><div><h3>Đánh giá của bạn</h3><p>{rating ? `${rating.avg_rating.toFixed(1)} / 5 · ${rating.rating_count} lượt đánh giá` : 'Đang tải đánh giá…'}</p></div></div>
          <div className="rating-stars" aria-label="Chọn số sao">
            {[1, 2, 3, 4, 5].map((score) => (
              <button aria-label={`${score} sao`} aria-pressed={rating?.my_score === score} className={rating && rating.my_score !== null && score <= rating.my_score ? 'star-selected' : ''} disabled={ratingBusy} key={score} onClick={() => void submitRating(score)}>★</button>
            ))}
          </div>
          {rating && <div className="rating-distribution">{[5, 4, 3, 2, 1].map((score) => <span key={score}>{score}★ {rating.distribution[String(score)] ?? 0}</span>)}</div>}
        </div>
        <div className="content-panel comments-panel">
          <div className="section-heading"><div><h3>Bình luận</h3><p>Chia sẻ câu hỏi hoặc điều bạn vừa khám phá.</p></div></div>
          <form className="comment-form" onSubmit={(event) => void submitComment(event)}>
            <textarea maxLength={1000} onChange={(event) => setCommentText(event.target.value)} placeholder="Viết bình luận…" required value={commentText} />
            <div><small>{commentText.length}/1000</small><button className="primary-button" disabled={commentBusy || !commentText.trim()} type="submit">{commentBusy ? 'Đang gửi…' : 'Gửi bình luận'}</button></div>
          </form>
          <div className="comment-list">
            {comments.map((comment) => (
              <article className="comment-item" key={comment.id}>
                <span className="avatar">{comment.author.username.slice(0, 1).toUpperCase()}</span>
                <div><div className="comment-heading"><strong>{comment.author.username}</strong><time dateTime={comment.created_at}>{humanDate(comment.created_at)}</time></div><p>{comment.content}</p>{comment.reply_count > 0 && <small>{comment.reply_count} phản hồi</small>}</div>
              </article>
            ))}
            {!comments.length && <p className="empty-state">Chưa có bình luận. Hãy bắt đầu cuộc trò chuyện!</p>}
          </div>
        </div>
      </section>
    </div>
  )
}

import type { AlgorithmDetail } from '../models/api'

type Props = {
  algorithm: AlgorithmDetail
}

// Phase 1 stub: route and layout are wired; real quiz UI ships in Phase 2.
export default function QuizPage({ algorithm }: Props) {
  return (
    <section className="workspace-section page-enter">
      <div className="section-heading">
        <div>
          <h2>Quiz – {algorithm.name}</h2>
          <p>Bài kiểm tra ngắn sẽ có ở bước tiếp theo.</p>
        </div>
      </div>
      <div className="content-panel quiz-placeholder">
        <p className="empty-state">Tính năng quiz đang được hoàn thiện.</p>
        <a className="primary-button" href={`/algorithm/${encodeURIComponent(algorithm.slug)}`}>
          ← Quay lại thuật toán
        </a>
      </div>
    </section>
  )
}
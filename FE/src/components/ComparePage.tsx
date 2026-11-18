import { useEffect, useMemo, useState } from 'react'
import type { AlgorithmSummary, CompareItem } from '../models/api'
import { ApiError } from '../services/apiClient'
import { compareAlgorithms, getAlgorithms } from '../services/contentService'

function messageFrom(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) return 'Không thể kết nối máy chủ.'
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi.'
}

function difficultyLabel(difficulty: AlgorithmSummary['difficulty']): string {
  return { EASY: 'Dễ', MEDIUM: 'Trung bình', HARD: 'Nâng cao' }[difficulty]
}

type Props = { ids: string[] }

export default function ComparePage({ ids: initialIds }: Props) {
  const [available, setAvailable] = useState<AlgorithmSummary[]>([])
  const [selected, setSelected] = useState<string[]>(() => [...new Set(initialIds)].slice(0, 4))
  const [pickerValue, setPickerValue] = useState('')
  const [comparison, setComparison] = useState<CompareItem[]>([])
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [loadingComparison, setLoadingComparison] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getAlgorithms({ page: 1, pageSize: 100, sort: 'name' })
      .then((result) => { if (active) setAvailable(result.data) })
      .catch((cause: unknown) => { if (active) setError(messageFrom(cause)) })
      .finally(() => { if (active) setLoadingOptions(false) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (selected.length < 2) {
      setComparison([])
      setLoadingComparison(false)
      return
    }
    let active = true
    setLoadingComparison(true)
    setError('')
    compareAlgorithms(selected)
      .then((result) => { if (active) setComparison(result.algorithms) })
      .catch((cause: unknown) => {
        if (active) {
          setComparison([])
          setError(messageFrom(cause))
        }
      })
      .finally(() => { if (active) setLoadingComparison(false) })
    return () => { active = false }
  }, [selected])

  const optionLookup = useMemo(
    () => new Map(available.flatMap((item) => [[item.slug, item.name], [String(item.id), item.name]])),
    [available],
  )
  const availableToAdd = available.filter((item) => !selected.includes(item.slug))

  function addSelected() {
    if (!pickerValue || selected.length >= 4) return
    setSelected((previous) => [...previous, pickerValue])
    setPickerValue('')
  }

  function removeSelected(value: string) {
    setSelected((previous) => previous.filter((item) => item !== value))
  }

  function submitComparison() {
    if (selected.length < 2) return
    window.location.href = `/compare?ids=${selected.map(encodeURIComponent).join(',')}`
  }

  return (
    <section className="workspace-section page-enter">
      <div className="section-heading">
        <div><h2>So sánh thuật toán</h2><p>Đặt từ hai đến bốn thuật toán cạnh nhau để xem điểm khác biệt.</p></div>
      </div>
      <div className="content-panel compare-picker">
        <div className="compare-picker-controls">
          <label htmlFor="compare-algorithm">Thêm thuật toán</label>
          <div>
            <select
              id="compare-algorithm"
              disabled={loadingOptions || selected.length >= 4 || availableToAdd.length === 0}
              onChange={(event) => setPickerValue(event.target.value)}
              value={pickerValue}
            >
              <option value="">{loadingOptions ? 'Đang tải…' : 'Chọn thuật toán'}</option>
              {availableToAdd.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}
            </select>
            <button className="secondary-button" disabled={!pickerValue || selected.length >= 4} onClick={addSelected} type="button">Thêm</button>
          </div>
        </div>
        <div className="compare-chips" aria-label="Thuật toán đã chọn">
          {selected.map((value) => (
            <span className="compare-chip" key={value}>
              {optionLookup.get(value) ?? value}
              <button aria-label={`Bỏ ${optionLookup.get(value) ?? value}`} onClick={() => removeSelected(value)} type="button">×</button>
            </span>
          ))}
          {!selected.length && <span className="compare-helper">Hãy chọn ít nhất hai thuật toán.</span>}
        </div>
        <button className="primary-button" disabled={selected.length < 2} onClick={submitComparison} type="button">So sánh</button>
        {selected.length < 2 && <p className="compare-helper">Chọn ít nhất 2 thuật toán và tối đa 4 thuật toán.</p>}
      </div>

      {error && <p className="notice-error" role="alert">{error}</p>}
      {loadingComparison && <div className="loading-state" role="status"><span className="loading-spinner" />Đang so sánh…</div>}
      {!loadingComparison && comparison.length >= 2 && (
        <div className="compare-table-wrap" role="region" aria-label="Bảng so sánh thuật toán" tabIndex={0}>
          <table className="compare-table">
            <thead><tr><th scope="col">Tiêu chí</th>{comparison.map((item) => <th scope="col" key={item.id}><a href={`/algorithm/${encodeURIComponent(item.slug)}`}>{item.name}</a></th>)}</tr></thead>
            <tbody>
              <tr><th scope="row">Danh mục</th>{comparison.map((item) => <td key={item.id}>{item.category}</td>)}</tr>
              <tr><th scope="row">Độ khó</th>{comparison.map((item) => <td key={item.id}><span className={`difficulty difficulty-${item.difficulty.toLowerCase()}`}>{difficultyLabel(item.difficulty)}</span></td>)}</tr>
              <tr><th scope="row">Thời gian tốt nhất</th>{comparison.map((item) => <td className="complexity-value" key={item.id}>{item.complexity.time_best}</td>)}</tr>
              <tr><th scope="row">Thời gian trung bình</th>{comparison.map((item) => <td className="complexity-value" key={item.id}>{item.complexity.time_average}</td>)}</tr>
              <tr><th scope="row">Thời gian xấu nhất</th>{comparison.map((item) => <td className="complexity-value" key={item.id}>{item.complexity.time_worst}</td>)}</tr>
              <tr><th scope="row">Bộ nhớ</th>{comparison.map((item) => <td className="complexity-value" key={item.id}>{item.complexity.space}</td>)}</tr>
              <tr><th scope="row">Đánh giá</th>{comparison.map((item) => <td key={item.id}>{item.avg_rating.toFixed(1)} ★ ({item.rating_count})</td>)}</tr>
              <tr><th scope="row">Mô phỏng</th>{comparison.map((item) => <td key={item.id}>{item.has_simulation ? 'Có' : 'Không'}</td>)}</tr>
              <tr><th scope="row">Thẻ</th>{comparison.map((item) => <td key={item.id}>{item.tags.length ? item.tags.map((tag) => tag.name).join(', ') : '—'}</td>)}</tr>
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

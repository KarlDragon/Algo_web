import { useEffect, useMemo, useState } from 'react'
import type { AlgorithmDetail } from '../models/api'

type Frame = {
  values: number[]
  active: number[]
  sorted: number[]
  message: string
  visited?: number[]
}

type Simulation = {
  kind: 'array' | 'graph' | 'unsupported'
  frames: Frame[]
}

const initialValues = [64, 34, 25, 78, 12, 92, 45, 56, 18, 83]
const graphEdges: Array<[number, number]> = [
  [0, 1], [0, 2], [1, 3], [1, 4], [2, 4], [2, 5], [3, 4], [4, 5],
]

function arraySimulation(slug: string, input: number[], target: number): Simulation {
  const values = [...input]
  const frames: Frame[] = [{ values: [...values], active: [], sorted: [], message: 'Dữ liệu ban đầu.' }]
  const sorted: number[] = []
  const record = (active: number[], message: string) => {
    frames.push({ values: [...values], active, sorted: [...sorted], message })
  }

  if (slug === 'bubble-sort') {
    for (let end = values.length - 1; end > 0; end -= 1) {
      let swapped = false
      for (let index = 0; index < end; index += 1) {
        record([index, index + 1], `So sánh ${values[index]} và ${values[index + 1]}.`)
        if (values[index] > values[index + 1]) {
          ;[values[index], values[index + 1]] = [values[index + 1], values[index]]
          swapped = true
          record([index, index + 1], 'Hoán đổi hai phần tử chưa đúng thứ tự.')
        }
      }
      sorted.unshift(end)
      if (!swapped) break
    }
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'selection-sort') {
    for (let start = 0; start < values.length - 1; start += 1) {
      let minimum = start
      for (let index = start + 1; index < values.length; index += 1) {
        record([minimum, index], `Tìm phần tử nhỏ nhất từ vị trí ${start}.`)
        if (values[index] < values[minimum]) minimum = index
      }
      ;[values[start], values[minimum]] = [values[minimum], values[start]]
      sorted.push(start)
      record([start, minimum], `Đưa ${values[start]} về vị trí ${start}.`)
    }
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'insertion-sort') {
    for (let index = 1; index < values.length; index += 1) {
      let current = index
      while (current > 0 && values[current - 1] > values[current]) {
        record([current - 1, current], 'So sánh phần tử hiện tại với phần đã sắp xếp.')
        ;[values[current - 1], values[current]] = [values[current], values[current - 1]]
        current -= 1
        record([current], 'Chèn phần tử vào đúng vị trí.')
      }
      sorted.splice(0, sorted.length, ...Array.from({ length: index + 1 }, (_, item) => item))
    }
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'merge-sort') {
    const mergeSort = (left: number, right: number) => {
      if (right - left < 2) return
      const middle = Math.floor((left + right) / 2)
      mergeSort(left, middle)
      mergeSort(middle, right)
      const merged: number[] = []
      let a = left
      let b = middle
      while (a < middle && b < right) {
        record([a, b], 'So sánh đầu hai nửa để trộn.')
        if (values[a] <= values[b]) merged.push(values[a++])
        else merged.push(values[b++])
      }
      merged.push(...values.slice(a, middle), ...values.slice(b, right))
      merged.forEach((value, offset) => { values[left + offset] = value })
      record(Array.from({ length: right - left }, (_, offset) => left + offset), 'Gộp hai nửa đã sắp xếp.')
    }
    mergeSort(0, values.length)
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'quick-sort') {
    const quickSort = (left: number, right: number) => {
      if (left >= right) return
      const pivot = values[right]
      let wall = left
      for (let index = left; index < right; index += 1) {
        record([index, right], `So sánh ${values[index]} với pivot ${pivot}.`)
        if (values[index] <= pivot) {
          ;[values[wall], values[index]] = [values[index], values[wall]]
          wall += 1
        }
      }
      ;[values[wall], values[right]] = [values[right], values[wall]]
      sorted.push(wall)
      record([wall], 'Đặt pivot vào vị trí chính xác.')
      quickSort(left, wall - 1)
      quickSort(wall + 1, right)
    }
    quickSort(0, values.length - 1)
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'linear-search') {
    let found = false
    for (let index = 0; index < values.length; index += 1) {
      record([index], `Kiểm tra giá trị ${values[index]}.`)
      if (values[index] === target) {
        sorted.push(index)
        record([index], `Tìm thấy ${target} ở vị trí ${index}.`)
        found = true
        break
      }
    }
    if (!found) record([], `Không tìm thấy ${target} trong mảng.`)
  } else if (slug === 'binary-search') {
    values.sort((a, b) => a - b)
    let left = 0
    let right = values.length - 1
    let found = false
    while (left <= right) {
      const middle = Math.floor((left + right) / 2)
      record([middle], `So sánh ${target} với phần tử giữa ${values[middle]}.`)
      if (values[middle] === target) {
        sorted.push(middle)
        record([middle], `Tìm thấy ${target} ở vị trí ${middle}.`)
        found = true
        break
      }
      if (values[middle] < target) left = middle + 1
      else right = middle - 1
    }
    if (!found) record([], `Không tìm thấy ${target} trong mảng.`)
  } else {
    return { kind: 'unsupported', frames: [] }
  }
  return { kind: 'array', frames }
}

function graphSimulation(slug: string): Simulation {
  if (slug !== 'bfs' && slug !== 'dfs') return { kind: 'unsupported', frames: [] }
  const adjacency = Array.from({ length: 6 }, () => [] as number[])
  graphEdges.forEach(([from, to]) => {
    adjacency[from].push(to)
    adjacency[to].push(from)
  })
  const frames: Frame[] = [{
    values: [], active: [0], sorted: [], visited: [], message: 'Bắt đầu từ đỉnh A.',
  }]
  const visited = new Set<number>([0])
  const pending = [0]
  const order: number[] = []
  while (pending.length) {
    const node = slug === 'bfs' ? pending.shift()! : pending.pop()!
    order.push(node)
    frames.push({
      values: [], active: [node], sorted: [...order], visited: [...visited],
      message: `Đang thăm đỉnh ${String.fromCharCode(65 + node)}.`,
    })
    const neighbors = slug === 'dfs' ? [...adjacency[node]].reverse() : adjacency[node]
    neighbors.forEach((neighbor) => {
      if (!visited.has(neighbor)) {
        visited.add(neighbor)
        pending.push(neighbor)
      }
    })
    frames.push({
      values: [], active: [], sorted: [...order], visited: [...visited],
      message: `Đã xếp các đỉnh chưa thăm vào ${slug === 'bfs' ? 'hàng đợi' : 'ngăn xếp'}.`,
    })
  }
  return { kind: 'graph', frames }
}

function createSimulation(algorithm: AlgorithmDetail, input: number[], target: number): Simulation {
  if (algorithm.slug === 'bfs' || algorithm.slug === 'dfs' || algorithm.slug === 'dijkstra') {
    return graphSimulation(algorithm.slug)
  }
  return arraySimulation(algorithm.slug, input, target)
}

function Bars({ frame }: { frame: Frame }) {
  const max = Math.max(...frame.values, 1)
  return (
    <div className="sim-bars" aria-label={`Mảng: ${frame.values.join(', ')}`}>
      {frame.values.map((value, index) => (
        <div className="sim-bar-column" key={`${index}-${value}`}>
          <span className="sim-value">{value}</span>
          <div
            className={`sim-bar${frame.sorted.includes(index) ? ' sim-bar-sorted' : frame.active.includes(index) ? ' sim-bar-active' : ''}`}
            style={{ height: `${Math.max(8, value / max * 82)}%` }}
          />
          <small>{index}</small>
        </div>
      ))}
    </div>
  )
}

function Graph({ frame }: { frame: Frame }) {
  return (
    <div className="sim-graph">
      {graphEdges.map(([from, to]) => <span className="graph-edge" key={`${from}-${to}`} />)}
      {Array.from({ length: 6 }, (_, index) => (
        <span className={`graph-node${frame.active.includes(index) ? ' graph-node-active' : frame.visited?.includes(index) ? ' graph-node-visited' : ''}`} key={index}>
          {String.fromCharCode(65 + index)}
        </span>
      ))}
    </div>
  )
}

export default function AlgorithmSimulator({ algorithm }: { algorithm: AlgorithmDetail }) {
  const [valuesText, setValuesText] = useState(initialValues.join(', '))
  const [targetText, setTargetText] = useState('45')
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [step, setStep] = useState(0)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const frame = simulation?.frames[step]
  const canSearch = algorithm.slug.includes('search')
  const allowedSlugs = useMemo(
    () => new Set(['bubble-sort', 'selection-sort', 'insertion-sort', 'merge-sort', 'quick-sort', 'linear-search', 'binary-search', 'bfs', 'dfs']),
    [],
  )

  useEffect(() => {
    setSimulation(null)
    setStep(0)
    setRunning(false)
  }, [algorithm.id])

  useEffect(() => {
    if (!running || !simulation) return
    const timer = window.setInterval(() => {
      setStep((current) => {
        if (current >= simulation.frames.length - 1) {
          setRunning(false)
          return current
        }
        return current + 1
      })
    }, 500)
    return () => window.clearInterval(timer)
  }, [running, simulation])

  function run() {
    const parsed = valuesText.split(',').map((item) => Number(item.trim()))
    if (parsed.length < 2 || parsed.length > 20 || parsed.some((value) => !Number.isFinite(value))) {
      setError('Nhập từ 2 đến 20 số, phân tách bằng dấu phẩy.')
      return
    }
    const target = Number(targetText)
    if (canSearch && !Number.isFinite(target)) {
      setError('Giá trị cần tìm phải là một số hợp lệ.')
      return
    }
    const result = createSimulation(algorithm, parsed, target)
    setSimulation(result)
    setStep(0)
    setRunning(false)
    setError('')
  }

  if (!allowedSlugs.has(algorithm.slug)) {
    return (
      <section className="simulator-panel">
        <div className="section-heading"><div><h3>Mô phỏng từng bước</h3><p>Mô phỏng được đánh dấu cho nội dung này nhưng chưa có bộ trực quan hóa tương ứng ở giao diện.</p></div></div>
      </section>
    )
  }

  return (
    <section className="simulator-panel">
      <div className="section-heading"><div><h3>Mô phỏng tương tác</h3><p>Điều khiển từng bước và quan sát thuật toán xử lý dữ liệu ngay trên trình duyệt.</p></div><span className="sim-local-badge">Xử lý tại trình duyệt</span></div>
      <div className="sim-inputs">
        <label>Dữ liệu đầu vào<input aria-label="Mảng số" onChange={(event) => setValuesText(event.target.value)} value={valuesText} /></label>
        {canSearch && <label>Giá trị cần tìm<input aria-label="Giá trị cần tìm" onChange={(event) => setTargetText(event.target.value)} type="number" value={targetText} /></label>}
        <button className="primary-button" onClick={run}>Tạo mô phỏng</button>
      </div>
      {error && <p className="sim-error" role="alert">{error}</p>}
      {simulation?.kind === 'unsupported' && <p className="sim-error">Chưa có mô phỏng phù hợp cho thuật toán này.</p>}
      {frame && simulation?.kind !== 'unsupported' && (
        <>
          <div className="sim-stage">
            {simulation?.kind === 'graph' ? <Graph frame={frame} /> : <Bars frame={frame} />}
          </div>
          <p className="sim-description" aria-live="polite">{frame.message}</p>
          <div className="sim-controls">
            <button disabled={step === 0} onClick={() => { setRunning(false); setStep(0) }}>⏮</button>
            <button disabled={step === 0} onClick={() => { setRunning(false); setStep((current) => Math.max(0, current - 1)) }}>←</button>
            <button className="primary-button" onClick={() => setRunning((value) => !value)}>{running ? 'Tạm dừng' : step >= (simulation?.frames.length ?? 1) - 1 ? 'Phát lại' : 'Tiếp tục'}</button>
            <button disabled={step >= (simulation?.frames.length ?? 1) - 1} onClick={() => { setRunning(false); setStep((current) => Math.min((simulation?.frames.length ?? 1) - 1, current + 1)) }}>→</button>
            <span>Bước {step + 1} / {simulation?.frames.length ?? 0}</span>
          </div>
        </>
      )}
    </section>
  )
}

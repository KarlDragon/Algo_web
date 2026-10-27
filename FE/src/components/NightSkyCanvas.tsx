import { useEffect, useRef } from 'react'

type Particle = {
  sx: number
  sy: number
  sz: number
  th: number
  x: number
  y: number
  vy: number
  sp: number
  len: number
  l: number
  dx: number
  dy: number
  a: number
  b: number
  cap: boolean
}

type Star = {
  x: number
  y: number
  p: number
  s: number
}

function NightSkyCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvasRef.current) {
      return
    }

    const cv = canvasRef.current
    const context = cv.getContext('2d')
    if (!context) {
      return
    }

    const ctx = context
    let W = 0
    let H = 0
    let dpr: number

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = window.innerWidth
      H = window.innerHeight
      cv.width = W * dpr
      cv.height = H * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    window.addEventListener('resize', resize)
    resize()

    // ---- Cấu hình (chỉnh ở đây) ----
    const N = W < 700 ? 33 : 60
    const FALL = [70, 260]
    const CHARGE_UP = 0.4
    const CHARGE_DOWN = 0.35
    const ROT = 0.45
    const TILT = 0.38
    const BUCKETS = 5
    const LEN = 4
    const RANGE_K = 0.28

    const ga = Math.PI * (3 - Math.sqrt(5))
    const ps: Particle[] = []

    for (let i = 0; i < N; i++) {
      const y = 1 - (2 * (i + 0.5)) / N
      const r = Math.sqrt(1 - y * y)
      const t = ga * i
      ps.push({
        sx: Math.cos(t) * r,
        sy: y,
        sz: Math.sin(t) * r,
        th: Math.random() * 0.85,
        x: Math.random() * W,
        y: Math.random() * H,
        vy: 0,
        sp: FALL[0] + Math.random() * (FALL[1] - FALL[0]),
        len: (8 + Math.random() * 16) * LEN,
        l: 12 * LEN,
        dx: 0,
        dy: -1,
        a: 0.3 + Math.random() * 0.6,
        b: 0,
        cap: false,
      })
    }

    const stars: Star[] = []
    for (let i = 0; i < 90; i++) {
      stars.push({
        x: Math.random(),
        y: Math.random() * 0.9,
        p: Math.random() * 6.28,
        s: Math.random() * 0.8 + 0.4,
      })
    }

    let mx = W / 2
    let my = H / 2
    let cx = mx
    let cy = my
    let last = -1e9
    let charge = 0
    let prev = performance.now()
    let time = 0
    let animationFrame = 0

    function move(e: PointerEvent) {
      mx = e.clientX
      my = e.clientY
      last = performance.now()
    }

    window.addEventListener('pointermove', move)
    window.addEventListener('pointerdown', move)

    function frame(now: number) {
      const dt = Math.min((now - prev) / 1000, 0.05)
      prev = now
      time += dt
      ctx.clearRect(0, 0, W, H)

      ctx.fillStyle = '#cfe4ff'
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i]
        ctx.globalAlpha =
          0.25 +
          0.35 *
            Math.sin(time * s.s + s.p) *
            Math.sin(time * s.s + s.p)
        ctx.fillRect(s.x * W, s.y * H, 1.2, 1.2)
      }

      const active = now - last < 1500
      charge += (active ? CHARGE_UP : -CHARGE_DOWN) * dt
      charge = Math.max(0, Math.min(1, charge))
      const k = 1 - Math.exp(-6 * dt)
      cx += (mx - cx) * k
      cy += (my - cy) * k

      const R = Math.max(64, Math.min(W, H) * 0.141)
      const RANGE = Math.max(140, Math.min(W, H) * RANGE_K)
      const ang = time * ROT
      const ca = Math.cos(ang)
      const sa = Math.sin(ang)
      const ct = Math.cos(TILT)
      const st = Math.sin(TILT)
      const kd = 1 - Math.exp(-8 * dt)

      for (let i = 0; i < N; i++) {
        const p = ps[i]
        let tdx: number
        let tdy: number
        let tl: number
        let alpha: number

        if (charge <= p.th) p.cap = false
        else if (!p.cap && Math.hypot(p.x - cx, p.y - cy) < RANGE) {
          p.cap = true
        }

        if (p.cap) {
          const x1 = p.sx * ca + p.sz * sa
          const z1 = -p.sx * sa + p.sz * ca
          const y2 = p.sy * ct - z1 * st
          const z2 = p.sy * st + z1 * ct
          const d = (z2 + 1) / 2
          const sc = 0.8 + 0.4 * d
          const tx = cx + x1 * R * sc
          const ty = cy + y2 * R * sc
          const e = 1 - Math.exp(-(2.5 + p.sp / 60) * dt)
          p.x += (tx - p.x) * e
          p.y += (ty - p.y) * e
          p.vy = 0
          const m = Math.hypot(x1, y2) + 1e-4
          tdx = x1 / m
          tdy = y2 / m
          tl = p.len * 0.45 * (0.35 + 0.65 * m) * sc
          alpha = Math.min(1, p.a * 0.35 + 0.25 + 0.55 * d)
        } else {
          p.vy += (p.sp - p.vy) * (1 - Math.exp(-2 * dt))
          p.y += p.vy * dt
          tdx = 0
          tdy = -1
          tl = p.len
          alpha = p.a
          if (p.y - p.len > H) {
            p.y = -p.len - Math.random() * H * 0.3
            p.x = Math.random() * W
          }
        }

        p.dx += (tdx - p.dx) * kd
        p.dy += (tdy - p.dy) * kd
        p.l += (tl - p.l) * kd
        p.b = Math.min(BUCKETS - 1, (alpha * BUCKETS) | 0)
      }

      ctx.lineCap = 'round'
      ctx.lineWidth = 1.4
      for (let b = 0; b < BUCKETS; b++) {
        ctx.globalAlpha = (b + 1) / BUCKETS
        ctx.strokeStyle = `hsl(200,90%,${66 + b * 4}%)`
        ctx.beginPath()
        for (let i = 0; i < N; i++) {
          const q = ps[i]
          if (q.b !== b) continue
          ctx.moveTo(q.x, q.y)
          ctx.lineTo(q.x + q.dx * q.l, q.y + q.dy * q.l)
        }
        ctx.stroke()
      }

      ctx.globalAlpha = 1
      animationFrame = window.requestAnimationFrame(frame)
    }

    animationFrame = window.requestAnimationFrame(frame)

    return () => {
      window.cancelAnimationFrame(animationFrame)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerdown', move)
    }
  }, [])

  return <canvas aria-hidden="true" className="night-sky-canvas" ref={canvasRef} />
}

export default NightSkyCanvas

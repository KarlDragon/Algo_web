import Link from 'next/link'

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[50vh] max-w-2xl flex-col items-center justify-center px-8 py-16 text-center">
      <span className="mb-5 font-mono text-6xl font-semibold text-violet-400/60">404</span>
      <h1 className="text-2xl font-semibold tracking-tight">Một nhánh chưa được khám phá</h1>
      <p className="mt-4 text-sm leading-7 text-slate-500">
        Trang này không tồn tại. Hãy quay về và tiếp tục hành trình thuật toán của bạn.
      </p>
      <Link
        className="mt-6 rounded-lg bg-violet-500/15 px-5 py-3 text-sm font-medium text-violet-300 transition hover:bg-violet-500/25"
        href="/"
      >
        &larr; Về trang chủ
      </Link>
    </main>
  )
}

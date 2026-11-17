// Algo_web — k6 load test. Use only against a local/test server you own.
// Run: k6 run -e BASE_URL=http://127.0.0.1:8000 -e ACCESS_TOKEN=<token> scripts/load_test.js
// Do not commit a real access token or write it into the source file.
import http from 'k6/http';
import { check, sleep } from 'k6';

const base = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const token = __ENV.ACCESS_TOKEN || '';
if (!token) {
  throw new Error('Thiếu ACCESS_TOKEN. Đăng nhập qua Swagger và truyền bằng -e ACCESS_TOKEN=...');
}

export const options = {
  stages: [
    { duration: '20s', target: 5 },
    { duration: '40s', target: 10 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000'], // TODO: mục tiêu phần lớn request dưới 3s
    http_req_failed: ['rate<0.01'],
  },
};

const paths = [
  '/home',
  '/categories',
  '/algorithms?page=1&page_size=20',
  '/search?q=bubble&page=1&page_size=20',
];

export default function () {
  const path = paths[__ITER % paths.length];
  const res = http.get(base + path, {
    headers: { Authorization: `Bearer ${token}` },
    tags: { endpoint: path.split('?')[0] },
    timeout: '10s',
  });
  check(res, { 'HTTP 200': (r) => r.status === 200 });
  sleep(1);
}

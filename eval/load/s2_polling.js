// S2 polling: GET /jobs/{id}. Mengukur RPS dan jumlah command Upstash per polling (budget 500 ribu per bulan).
// Env tambahan: JOB_ID (job yang sudah ada milik user TOKEN).
import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TOKEN, DEFAULT_THRESHOLDS, authHeaders } from './common.js';

const JOB_ID = __ENV.JOB_ID || '';

export const options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '2m', target: 20 },
    { duration: '15s', target: 0 },
  ],
  thresholds: { ...DEFAULT_THRESHOLDS, http_req_duration: ['p(95)<800'] },
};

export function setup() {
  if (!TOKEN || !JOB_ID) throw new Error('set TOKEN dan JOB_ID');
}

export default function () {
  const res = http.get(`${BASE_URL}/jobs/${JOB_ID}?after_seq=0`, { headers: authHeaders() });
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1); // polling dashboard: sekitar 1 detik, sesuai Architecture.md 8.5
}

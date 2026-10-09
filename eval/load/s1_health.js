// S1 baseline: GET /health. Mengukur latensi dasar dan cold start Lambda.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, DEFAULT_THRESHOLDS } from './common.js';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 10 },
    { duration: '15s', target: 0 },
  ],
  thresholds: { ...DEFAULT_THRESHOLDS, http_req_duration: ['p(95)<1000'] },
};

export default function () {
  const res = http.get(`${BASE_URL}/health`);
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(0.5);
}

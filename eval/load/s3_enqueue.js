// S3 enqueue: POST /chat. Mengukur rasio 202 dan batas rl:chat (20 per jam per user).
// Jalankan dengan mock gateway LLM atau dengan worker dinonaktifkan agar tidak memakai kuota LLM.
// Env tambahan: none. Setiap request memakai client_request_id unik.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';
import { BASE_URL, authHeaders } from './common.js';

const accepted = new Counter('chat_accepted_202');
const quota = new Counter('chat_quota_429');

export const options = {
  scenarios: {
    enqueue: {
      executor: 'constant-arrival-rate',
      rate: 2,
      timeUnit: '1m',
      duration: '5m',
      preAllocatedVUs: 5,
      maxVUs: 10,
    },
  },
  thresholds: { http_req_failed: ['rate<0.05'] },
};

export default function () {
  const body = JSON.stringify({
    question: 'Bagaimana kondisi BTC minggu ini?',
    client_request_id: `k6-${__VU}-${__ITER}-${Date.now()}`,
  });
  const res = http.post(`${BASE_URL}/chat`, body, { headers: authHeaders() });
  if (res.status === 202) accepted.add(1);
  if (res.status === 429) quota.add(1);
  check(res, { 'accepted or quota': (r) => r.status === 202 || r.status === 429 });
  sleep(1);
}

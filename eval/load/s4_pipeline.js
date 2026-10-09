// S4 pipeline: throughput job worker. Mengirim job lalu polling sampai status terminal.
// Mengukur durasi end-to-end per job, sehingga throughput per menit bisa dihitung dari hasil.
// Mengukur antrean SQS: kenaikan durasi saat rate dinaikkan menunjukkan titik jenuh (Little's law).
// Jalankan dengan LLM mock, karena setiap job memakai panggilan gateway.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';
import { BASE_URL, authHeaders } from './common.js';

const jobDuration = new Trend('job_end_to_end_ms', true);
const TERMINAL = ['completed', 'blocked', 'insufficient', 'handoff', 'failed', 'cancelled'];

export const options = {
  scenarios: {
    pipeline: {
      executor: 'constant-vus',
      vus: 2,
      duration: '10m',
    },
  },
  thresholds: { job_end_to_end_ms: ['p(95)<100000'] }, // batas 100 detik per job (Architecture.md 3.2)
};

export default function () {
  const start = Date.now();
  const post = http.post(
    `${BASE_URL}/chat`,
    JSON.stringify({
      question: 'Ringkas posisi portofolio saya.',
      client_request_id: `s4-${__VU}-${__ITER}-${start}`,
    }),
    { headers: authHeaders() },
  );
  if (!check(post, { 'enqueued': (r) => r.status === 202 })) {
    sleep(5);
    return;
  }
  const jobId = post.json('job_id');

  let status = '';
  for (let i = 0; i < 60 && !TERMINAL.includes(status); i++) {
    sleep(2);
    const res = http.get(`${BASE_URL}/jobs/${jobId}`, { headers: authHeaders() });
    status = res.json('status') || '';
  }
  jobDuration.add(Date.now() - start);
  check(status, { 'terminal': (s) => TERMINAL.includes(s) });
}

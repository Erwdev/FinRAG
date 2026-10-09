// Konfigurasi bersama untuk skenario k6 (Improvisation 4.2).
// Env yang dibutuhkan:
//   BASE_URL   Function URL finrag-api, tanpa slash di akhir
//   TOKEN      JWT Clerk milik user owner (jangan commit)
export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
export const TOKEN = __ENV.TOKEN || '';

export function authHeaders() {
  return { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' };
}

// Ambang default. Angka ini ditentukan setelah pengukuran pertama, bukan dari tebakan.
export const DEFAULT_THRESHOLDS = {
  http_req_failed: ['rate<0.01'],
};

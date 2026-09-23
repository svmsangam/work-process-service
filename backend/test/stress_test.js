import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 10 },  // Ramp-up to 10 VUs
    { duration: '20s', target: 50 },  // Spike to 50 VUs
    { duration: '10s', target: 0 },   // Cool-down
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],   // Less than 1% failed requests
    http_req_duration: ['p(95)<500'], // 95% of API requests should complete within 500ms
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const uniqueId = `LOAD-${Date.now()}-${Math.floor(Math.random() * 100000)}`;

  // 1. Test POST /work-items (Creation + Background Task Dispatch)
  const payload = JSON.stringify({
    external_id: uniqueId,
    title: `Load Test Item ${uniqueId}`,
    description: 'Performance testing FastAPI ingestion and OpenRouter background task queue.',
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  const createRes = http.post(`${BASE_URL}/work-items`, payload, params);

  check(createRes, {
    'create item status is 201': (r) => r.status === 201,
    'create item latency < 200ms': (r) => r.timings.duration < 200,
  });

  // 2. Test GET /work-items (List Fetching)
  const listRes = http.get(`${BASE_URL}/work-items`);

  check(listRes, {
    'get items status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
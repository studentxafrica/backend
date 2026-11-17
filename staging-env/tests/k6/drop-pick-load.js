// Load just after a 12:00 pick: members opening Festive Drops to see their
// result, the next drop and their perks.
//
//   k6 run -e RATE=60 -e TOKENS=path/to/tokens.json staging-env/tests/k6/drop-pick-load.js
//
// TOKENS is a JSON list of session tokens for joined members (made by the
// staging seed step); without it every request is a signed-out visitor.
import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://localhost:6060';
const RATE = parseInt(__ENV.RATE || '60', 10);
const tokens = __ENV.TOKENS ? JSON.parse(open(__ENV.TOKENS)) : [];
const pageTime = new Trend('drops_page', true);
const perksTime = new Trend('my_perks', true);

export const options = {
  scenarios: {
    after_pick: {
      executor: 'ramping-arrival-rate',
      startRate: 0,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 400,
      stages: [
        { duration: '20s', target: RATE },
        { duration: __ENV.HOLD || '1m', target: RATE },
        { duration: '10s', target: 0 },
      ],
    },
  },
};

export default function () {
  const token = tokens.length ? tokens[__ITER % tokens.length] : null;
  const headers = { 'X-Forwarded-For': `10.9.${__VU & 255}.${(__ITER % 250) + 1}` };
  if (token) headers.Authorization = `Bearer ${token}`;

  const page = http.get(`${BASE}/api/v1/drops/campaigns/studentxmas`, { headers });
  pageTime.add(page.timings.duration);
  check(page, { 'drops page loads': (r) => r.status === 200 });

  if (token) {
    const perks = http.get(`${BASE}/api/v1/drops/me/picks`, { headers });
    perksTime.add(perks.timings.duration);
    check(perks, { 'perks load': (r) => r.status === 200 });
  }
}

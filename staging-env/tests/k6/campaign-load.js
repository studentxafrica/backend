// Load test for a campaign burst: students signing up and uploading their
// student ID, while others browse the site.
//
//   k6 run -e PEAK=50 staging-env/tests/k6/campaign-load.js
//
// It talks to gunicorn directly and gives every virtual student its own
// address (X-Forwarded-For, which production trusts from nginx), so the
// per-address limits behave as they would for students on different networks.
// PEAK is the number of students signing up at the same moment.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://localhost:6060';
const PEAK = parseInt(__ENV.PEAK || '25', 10);
const HOLD = __ENV.HOLD || '2m';
const PHOTO_MB = parseFloat(__ENV.PHOTO_MB || '3');

const photo = new Uint8Array(Math.round(PHOTO_MB * 1024 * 1024)).buffer;

const signupTime = new Trend('signup_journey', true);
const uploadTime = new Trend('id_upload', true);
const browseTime = new Trend('browse', true);
const failedSignups = new Counter('failed_signups');
const completedSignups = new Counter('completed_signups');

export const options = {
  insecureSkipTLSVerify: true,
  discardResponseBodies: false,
  scenarios: {
    signups: {
      executor: 'ramping-vus',
      exec: 'signup',
      startVUs: 0,
      stages: [
        { duration: '30s', target: PEAK },
        { duration: HOLD, target: PEAK },
        { duration: '15s', target: 0 },
      ],
    },
    browsing: {
      executor: 'constant-arrival-rate',
      exec: 'browse',
      rate: parseInt(__ENV.BROWSE_RATE || '10', 10),
      timeUnit: '1s',
      duration: '3m',
      preAllocatedVUs: 20,
      maxVUs: 200,
    },
  },
};

function address() {
  return `10.${(__VU >> 8) & 255}.${__VU & 255}.${(__ITER % 250) + 1}`;
}

export function signup() {
  const id = `${__VU}-${__ITER}-${Date.now()}`;
  const email = `load-${id}@staging.invalid`;
  const headers = { 'Content-Type': 'application/json', 'X-Forwarded-For': address() };
  const started = Date.now();

  const checkEmail = http.post(`${BASE}/api/v1/auth/user/check-email`, JSON.stringify({ email }), { headers, tags: { step: 'check-email' } });
  const register = http.post(`${BASE}/api/v1/auth/user/consumer/register`, JSON.stringify({
    first_name: 'Load', last_name: `Student ${id}`, email, password: 'Load-test-pass-1', school: 'University of Nairobi',
  }), { headers, tags: { step: 'register' } });
  const ok = check(register, { 'registered': (r) => r.status === 201 }) &&
             check(checkEmail, { 'email check allowed': (r) => r.status === 200 });
  if (!ok) { failedSignups.add(1); return; }

  const cookie = register.cookies.access_token ? register.cookies.access_token[0].value : '';
  const authed = { 'X-Forwarded-For': headers['X-Forwarded-For'], Cookie: `access_token=${cookie}` };

  const uploadStarted = Date.now();
  const upload = http.post(`${BASE}/api/v1/user/verification/student/submit`, {
    documents: http.file(photo, 'student-id.jpg', 'image/jpeg'),
    personalInfo: JSON.stringify({ dateOfBirth: '2004-05-17' }),
    academicInfo: JSON.stringify({ university: 'University of Nairobi' }),
    documentsMeta: JSON.stringify([{ type: 'student_id' }]),
  }, { headers: authed, timeout: '180s', tags: { step: 'upload' } });
  uploadTime.add(Date.now() - uploadStarted);
  if (!check(upload, { 'ID uploaded': (r) => r.status === 201 })) { failedSignups.add(1); return; }

  const me = http.get(`${BASE}/api/v1/user/me`, { headers: authed, tags: { step: 'profile' } });
  check(me, { 'profile loads': (r) => r.status === 200 });
  signupTime.add(Date.now() - started);
  completedSignups.add(1);
  sleep(1);
}

export function browse() {
  const headers = { 'X-Forwarded-For': `172.16.${__VU & 255}.${(__ITER % 250) + 1}` };
  const pages = ['/api/v1/offer/latest', '/api/v1/offer/featured', '/api/v1/offer/highlighted', '/api/v1/category/all'];
  const r = http.get(`${BASE}${pages[__ITER % pages.length]}`, { headers, tags: { step: 'browse' } });
  browseTime.add(r.timings.duration);
  check(r, { 'page data loads': (res) => res.status === 200 });
}

// A small stateful HTTP API with the same contract as the real backend's
// public endpoints. The "full" Playwright lane runs against it. In your own
// repository, point the full lane at a real backend instead.
import { createServer } from 'node:http';

const PORT = Number(process.env.DEMO_API_PORT ?? 4010);

const seed = () => ({
  nextId: 100,
  employees: [
    { id: 1, employee_no: 'E00001', full_name: 'Lina Saeed', email: 'lina@acme.example', department: 'Engineering', status: 'active', monthly_salary: 25000 },
    { id: 2, employee_no: 'E00002', full_name: 'Ravi Menon', email: 'ravi@acme.example', department: 'Engineering', status: 'active', monthly_salary: 21000 },
    { id: 3, employee_no: 'E00003', full_name: 'Omar Haddad', email: 'omar@acme.example', department: 'Finance', status: 'active', monthly_salary: 18000 },
    { id: 4, employee_no: 'E00004', full_name: 'Maya Costa', email: 'maya@acme.example', department: 'People', status: 'terminated', monthly_salary: 15000 },
  ],
  leave: [
    { id: 10, employee_id: 2, employee_name: 'Ravi Menon', leave_type: 'sick', start_date: '2026-11-09', end_date: '2026-11-10', days: 2, status: 'pending' },
  ],
});
let state = seed();

function workingDays(start, end) {
  let count = 0;
  for (let d = new Date(`${start}T00:00:00Z`); d <= new Date(`${end}T00:00:00Z`); d = new Date(d.getTime() + 86_400_000)) {
    if (![0, 6].includes(d.getUTCDay())) count += 1;
  }
  return count;
}

const send = (res, status, body) => {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(body === undefined ? '' : JSON.stringify(body));
};

const readJson = (req) =>
  new Promise((resolve) => {
    let raw = '';
    req.on('data', (chunk) => (raw += chunk));
    req.on('end', () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch {
        resolve(null);
      }
    });
  });

createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const path = url.pathname;
  if (req.method === 'GET' && path === '/api/health') return send(res, 200, { status: 'ok' });
  if (req.method === 'POST' && path === '/api/__reset') {
    state = seed();
    return send(res, 200, { reset: true });
  }
  if (req.method === 'GET' && path === '/api/employees') return send(res, 200, state.employees);
  if (req.method === 'GET' && path === '/api/leave-requests') {
    const status = url.searchParams.get('status');
    return send(res, 200, state.leave.filter((l) => !status || l.status === status));
  }
  if (req.method === 'POST' && path === '/api/leave-requests') {
    const body = await readJson(req);
    const emp = state.employees.find((e) => e.id === body?.employee_id);
    if (!emp) return send(res, 422, { detail: 'unknown employee' });
    if (emp.status === 'terminated') return send(res, 409, { detail: 'employee is terminated' });
    const days = workingDays(body.start_date, body.end_date);
    if (days === 0) return send(res, 422, { detail: 'request covers no working days' });
    const clash = state.leave.some(
      (l) => l.employee_id === emp.id && ['pending', 'approved'].includes(l.status) && l.start_date <= body.end_date && l.end_date >= body.start_date,
    );
    if (clash) return send(res, 409, { detail: 'overlaps an existing request' });
    const row = { id: state.nextId++, employee_id: emp.id, employee_name: emp.full_name, leave_type: body.leave_type, start_date: body.start_date, end_date: body.end_date, days, status: 'pending' };
    state.leave.push(row);
    return send(res, 201, row);
  }
  const m = path.match(/^\/api\/leave-requests\/(\d+)\/(approve|reject)$/);
  if (req.method === 'POST' && m) {
    const row = state.leave.find((l) => l.id === Number(m[1]));
    if (!row) return send(res, 404, { detail: 'leave request not found' });
    if (row.status !== 'pending') return send(res, 409, { detail: `cannot move from ${row.status}` });
    row.status = m[2] === 'approve' ? 'approved' : 'rejected';
    return send(res, 200, row);
  }
  send(res, 404, { detail: 'not found' });
}).listen(PORT, '127.0.0.1', () => console.log(`demo API on http://127.0.0.1:${PORT}`));

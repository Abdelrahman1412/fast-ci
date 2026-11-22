import { api, ApiError, type LeaveRequest } from './api';
import { workingDays } from './lib/dates';
import { headcountByDepartment, searchEmployees, sortEmployees, type Employee, type SortKey } from './lib/employees';
import { formatMoney } from './lib/money';
import { estimateNet } from './lib/payroll';
import { isValid, validateLeave, type LeaveForm } from './lib/validation';

const app = document.querySelector<HTMLDivElement>('#app')!;

const esc = (value: unknown) =>
  String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

const pages: Record<string, { title: string; render: (root: HTMLElement) => Promise<void> | void }> = {
  '#/employees': { title: 'Employees', render: employeesPage },
  '#/leave': { title: 'Leave requests', render: leavePage },
  '#/leave/new': { title: 'New request', render: newLeavePage },
  '#/payslip': { title: 'Payslip estimate', render: payslipPage },
};

function shell(active: string): HTMLElement {
  const nav = Object.entries(pages)
    .map(([hash, p]) => `<a href="${hash}"${hash === active ? ' aria-current="page"' : ''}>${p.title}</a>`)
    .join('');
  app.innerHTML = `<header><strong>Acme HR</strong><nav>${nav}</nav></header><main></main>`;
  return app.querySelector('main')!;
}

async function route(): Promise<void> {
  const hash = pages[location.hash] ? location.hash : '#/employees';
  const root = shell(hash);
  document.title = `${pages[hash].title} · Acme HR`;
  try {
    await pages[hash].render(root);
  } catch (err) {
    const message = err instanceof ApiError ? `The server said: ${err.message}` : 'Something went wrong.';
    root.innerHTML = `<p role="alert" class="error">${esc(message)}</p>`;
  }
}

async function employeesPage(root: HTMLElement): Promise<void> {
  root.innerHTML = '<h1>Employees</h1><p>Loading…</p>';
  const all = await api.employees();
  let query = '';
  let sortKey: SortKey = 'name';
  const counts = headcountByDepartment(all);
  root.innerHTML = `
    <h1>Employees</h1>
    <section class="card" aria-label="Headcount">
      ${Object.entries(counts).map(([d, n]) => `<span data-testid="headcount">${esc(d)}: ${n}</span>`).join(' · ') || '<span class="empty">No active employees</span>'}
    </section>
    <label>Search <input name="search" type="search" /></label>
    <label>Sort by <select name="sort"><option value="name">Name</option><option value="number">Number</option><option value="salary">Salary</option></select></label>
    <table><thead><tr><th>No.</th><th>Name</th><th>Department</th><th>Status</th><th>Salary</th></tr></thead><tbody></tbody></table>`;
  const tbody = root.querySelector('tbody')!;
  const draw = () => {
    const rows = sortEmployees(searchEmployees(all, query), sortKey);
    tbody.innerHTML = rows.length
      ? rows
          .map(
            (e: Employee) =>
              `<tr><td>${esc(e.employee_no)}</td><td>${esc(e.full_name)}</td><td>${esc(e.department)}</td><td>${esc(e.status)}</td><td>${formatMoney(e.monthly_salary)}</td></tr>`,
          )
          .join('')
      : '<tr><td colspan="5" class="empty">No employees match</td></tr>';
  };
  root.querySelector<HTMLInputElement>('input[name=search]')!.addEventListener('input', (ev) => {
    query = (ev.target as HTMLInputElement).value;
    draw();
  });
  root.querySelector<HTMLSelectElement>('select[name=sort]')!.addEventListener('change', (ev) => {
    sortKey = (ev.target as HTMLSelectElement).value as SortKey;
    draw();
  });
  draw();
}

async function leavePage(root: HTMLElement): Promise<void> {
  const status = new URLSearchParams(location.search).get('status') ?? 'pending';
  const rows = await api.leaveRequests(status);
  root.innerHTML = `<h1>Leave requests</h1><p><a href="#/leave/new">New request</a></p><div aria-live="polite" id="flash"></div><table><thead><tr><th>Employee</th><th>Type</th><th>Dates</th><th>Days</th><th>Status</th><th></th></tr></thead><tbody></tbody></table>`;
  const tbody = root.querySelector('tbody')!;
  const flash = root.querySelector('#flash')!;
  const row = (r: LeaveRequest) =>
    `<tr data-id="${r.id}"><td>${esc(r.employee_name)}</td><td>${esc(r.leave_type)}</td><td>${esc(r.start_date)} → ${esc(r.end_date)}</td><td>${r.days}</td><td class="status">${esc(r.status)}</td><td>${
      r.status === 'pending'
        ? `<button data-action="approve">Approve</button> <button data-action="reject">Reject</button>`
        : ''
    }</td></tr>`;
  tbody.innerHTML = rows.length ? rows.map(row).join('') : '<tr><td colspan="6" class="empty">Nothing to review</td></tr>';
  tbody.addEventListener('click', async (ev) => {
    const button = (ev.target as HTMLElement).closest<HTMLButtonElement>('button[data-action]');
    if (!button) return;
    const tr = button.closest<HTMLTableRowElement>('tr')!;
    const action = button.dataset.action as 'approve' | 'reject';
    try {
      const updated = await api.decide(Number(tr.dataset.id), action);
      tr.outerHTML = row(updated);
      flash.innerHTML = `<p class="notice">Request ${action === 'approve' ? 'approved' : 'rejected'}.</p>`;
    } catch (err) {
      flash.innerHTML = `<p role="alert" class="error">${esc(err instanceof ApiError ? err.message : 'Could not update the request')}</p>`;
    }
  });
}

async function newLeavePage(root: HTMLElement): Promise<void> {
  const employees = await api.employees();
  root.innerHTML = `
    <h1>New leave request</h1>
    <form novalidate>
      <label>Employee <select name="employeeId"><option value="">Choose…</option>${employees
        .filter((e) => e.status !== 'terminated')
        .map((e) => `<option value="${e.id}">${esc(e.full_name)}</option>`)
        .join('')}</select></label>
      <label>Type <select name="leaveType"><option value="">Choose…</option><option value="annual">Annual</option><option value="sick">Sick</option><option value="unpaid">Unpaid</option></select></label>
      <label>From <input name="startDate" type="date" /></label>
      <label>To <input name="endDate" type="date" /></label>
      <label>Reason <textarea name="reason"></textarea></label>
      <p data-testid="days-preview"></p>
      <ul class="error" data-testid="errors"></ul>
      <button type="submit">Submit request</button>
    </form><div id="result" aria-live="polite"></div>`;
  const form = root.querySelector('form')!;
  const read = (): LeaveForm => {
    const data = new FormData(form);
    return {
      employeeId: String(data.get('employeeId') ?? ''),
      leaveType: String(data.get('leaveType') ?? ''),
      startDate: String(data.get('startDate') ?? ''),
      endDate: String(data.get('endDate') ?? ''),
      reason: String(data.get('reason') ?? ''),
    };
  };
  const preview = root.querySelector('[data-testid=days-preview]')!;
  form.addEventListener('input', () => {
    const f = read();
    try {
      preview.textContent = `${workingDays(f.startDate, f.endDate)} working day(s)`;
    } catch {
      preview.textContent = '';
    }
  });
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const f = read();
    const errors = validateLeave(f);
    root.querySelector('[data-testid=errors]')!.innerHTML = Object.values(errors)
      .map((m) => `<li>${esc(m)}</li>`)
      .join('');
    if (!isValid(errors)) return;
    const result = root.querySelector('#result')!;
    try {
      const created = await api.createLeave({
        employee_id: Number(f.employeeId),
        leave_type: f.leaveType,
        start_date: f.startDate,
        end_date: f.endDate,
        reason: f.reason,
      });
      result.innerHTML = `<p class="notice">Request #${created.id} submitted for ${created.days} day(s).</p>`;
      form.reset();
    } catch (err) {
      result.innerHTML = `<p role="alert" class="error">${esc(err instanceof ApiError ? err.message : 'Could not submit')}</p>`;
    }
  });
}

function payslipPage(root: HTMLElement): void {
  root.innerHTML = `
    <h1>Payslip estimate</h1>
    <form>
      <label>Basic <input name="basic" inputmode="decimal" value="12000" /></label>
      <label>Housing <input name="housing" inputmode="decimal" value="3000" /></label>
      <label>Transport <input name="transport" inputmode="decimal" value="1000" /></label>
      <label>Month <input name="month" type="month" value="2026-04" /></label>
    </form>
    <dl class="card"><dt>Gross</dt><dd data-testid="gross"></dd><dt>Deductions</dt><dd data-testid="deductions"></dd><dt>Net</dt><dd data-testid="net"></dd></dl>`;
  const form = root.querySelector('form')!;
  const draw = () => {
    const data = new FormData(form);
    const [year, month] = String(data.get('month')).split('-').map(Number);
    const num = (k: string) => Number(data.get(k)) || 0;
    const r = estimateNet({ basic: num('basic'), housing: num('housing'), transport: num('transport'), year, month });
    root.querySelector('[data-testid=gross]')!.textContent = formatMoney(r.gross);
    root.querySelector('[data-testid=deductions]')!.textContent = formatMoney(r.deductions);
    root.querySelector('[data-testid=net]')!.textContent = formatMoney(r.net);
  };
  form.addEventListener('input', draw);
  draw();
}

window.addEventListener('hashchange', route);
void route();

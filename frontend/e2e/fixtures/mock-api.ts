import { test as base, type Page, type Route } from '@playwright/test';
import type { LeaveRequest } from '../../src/api';
import type { Employee } from '../../src/lib/employees';
import { employees, pendingLeave } from './data';

type Handler = (route: Route, body: unknown) => Promise<void> | void;

export interface MockApi {
  employees: Employee[];
  leave: LeaveRequest[];
  /** Override one endpoint, e.g. to return an error. Key: "METHOD /path". */
  on(key: string, handler: Handler): void;
  /** Every call the page made, in order. */
  calls: string[];
  /** Calls no handler matched. A non-empty list fails the test. */
  unhandled: string[];
}

const json = (route: Route, status: number, body: unknown) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

async function install(page: Page): Promise<MockApi> {
  const overrides = new Map<string, Handler>();
  const api: MockApi = {
    employees: structuredClone(employees),
    leave: structuredClone(pendingLeave),
    on: (key, handler) => void overrides.set(key, handler),
    calls: [],
    unhandled: [],
  };
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const key = `${request.method()} ${url.pathname.replace(/^\/api/, '')}`;
    api.calls.push(key);
    const body = request.postData() ? JSON.parse(request.postData()!) : undefined;
    const override = overrides.get(key);
    if (override) return override(route, body);
    if (key === 'GET /employees') return json(route, 200, api.employees);
    if (key === 'GET /leave-requests') {
      const status = url.searchParams.get('status');
      return json(route, 200, api.leave.filter((l) => !status || l.status === status));
    }
    if (key === 'POST /leave-requests') {
      const b = body as { employee_id: number; leave_type: string; start_date: string; end_date: string };
      const emp = api.employees.find((e) => e.id === b.employee_id)!;
      const row: LeaveRequest = { id: 99, employee_id: emp.id, employee_name: emp.full_name, leave_type: b.leave_type, start_date: b.start_date, end_date: b.end_date, days: 3, status: 'pending' };
      api.leave.push(row);
      return json(route, 201, row);
    }
    const decision = key.match(/^POST \/leave-requests\/(\d+)\/(approve|reject)$/);
    if (decision) {
      const row = api.leave.find((l) => l.id === Number(decision[1]))!;
      row.status = decision[2] === 'approve' ? 'approved' : 'rejected';
      return json(route, 200, row);
    }
    // An unmocked call is a test bug: abort it and fail the test at teardown.
    api.unhandled.push(key);
    return route.abort('failed');
  });
  return api;
}

export const test = base.extend<{ mockApi: MockApi }>({
  mockApi: [
    async ({ page }, use) => {
      const api = await install(page);
      await use(api);
      if (api.unhandled.length) throw new Error(`mock lane: no handler for ${api.unhandled.join(', ')}`);
    },
    { auto: true },
  ],
});

export { expect } from '@playwright/test';

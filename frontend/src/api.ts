import type { Employee } from './lib/employees';

export interface LeaveRequest {
  id: number;
  employee_id: number;
  employee_name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days: number;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, (body as { detail?: string } | null)?.detail ?? res.statusText);
  return body as T;
}

export const api = {
  employees: () => call<Employee[]>('/employees'),
  leaveRequests: (status?: string) => call<LeaveRequest[]>(`/leave-requests${status ? `?status=${status}` : ''}`),
  createLeave: (body: object) => call<LeaveRequest>('/leave-requests', { method: 'POST', body: JSON.stringify(body) }),
  decide: (id: number, action: 'approve' | 'reject') =>
    call<LeaveRequest>(`/leave-requests/${id}/${action}`, { method: 'POST' }),
};

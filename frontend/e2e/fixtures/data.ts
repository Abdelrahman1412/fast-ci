import type { LeaveRequest } from '../../src/api';
import type { Employee } from '../../src/lib/employees';

export const employees: Employee[] = [
  { id: 1, employee_no: 'E00001', full_name: 'Lina Saeed', email: 'lina@acme.example', department: 'Engineering', status: 'active', monthly_salary: 25000 },
  { id: 2, employee_no: 'E00002', full_name: 'Ravi Menon', email: 'ravi@acme.example', department: 'Engineering', status: 'on_leave', monthly_salary: 21000 },
  { id: 3, employee_no: 'E00003', full_name: 'Omar Haddad', email: 'omar@acme.example', department: 'Finance', status: 'active', monthly_salary: 18000 },
  { id: 4, employee_no: 'E00004', full_name: 'Maya Costa', email: 'maya@acme.example', department: 'People', status: 'terminated', monthly_salary: 15000 },
];

export const pendingLeave: LeaveRequest[] = [
  { id: 11, employee_id: 1, employee_name: 'Lina Saeed', leave_type: 'annual', start_date: '2026-12-07', end_date: '2026-12-11', days: 5, status: 'pending' },
  { id: 12, employee_id: 3, employee_name: 'Omar Haddad', leave_type: 'sick', start_date: '2026-11-16', end_date: '2026-11-16', days: 1, status: 'pending' },
];

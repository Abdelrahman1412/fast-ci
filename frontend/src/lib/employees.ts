export interface Employee {
  id: number;
  employee_no: string;
  full_name: string;
  email: string;
  department: string;
  status: 'active' | 'on_leave' | 'terminated';
  monthly_salary: number;
}

export type SortKey = 'name' | 'number' | 'salary';

export function searchEmployees(rows: Employee[], query: string): Employee[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((e) =>
    [e.full_name, e.employee_no, e.email, e.department].some((field) => field.toLowerCase().includes(needle)),
  );
}

export function sortEmployees(rows: Employee[], key: SortKey, descending = false): Employee[] {
  const sorted = [...rows].sort((a, b) => {
    if (key === 'salary') return a.monthly_salary - b.monthly_salary;
    if (key === 'number') return a.employee_no.localeCompare(b.employee_no);
    return a.full_name.localeCompare(b.full_name);
  });
  return descending ? sorted.reverse() : sorted;
}

export function headcountByDepartment(rows: Employee[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const e of rows) {
    if (e.status === 'terminated') continue;
    counts[e.department] = (counts[e.department] ?? 0) + 1;
  }
  return counts;
}

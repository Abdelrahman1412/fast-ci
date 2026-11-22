import { describe, expect, it } from 'vitest';
import { headcountByDepartment, searchEmployees, sortEmployees, type Employee } from './employees';

const people: Employee[] = [
  { id: 1, employee_no: 'E00003', full_name: 'Omar Haddad', email: 'omar@acme.example', department: 'Finance', status: 'active', monthly_salary: 18000 },
  { id: 2, employee_no: 'E00001', full_name: 'Lina Saeed', email: 'lina@acme.example', department: 'Engineering', status: 'active', monthly_salary: 25000 },
  { id: 3, employee_no: 'E00002', full_name: 'Ravi Menon', email: 'ravi@acme.example', department: 'Engineering', status: 'on_leave', monthly_salary: 21000 },
  { id: 4, employee_no: 'E00004', full_name: 'Maya Costa', email: 'maya@acme.example', department: 'People', status: 'terminated', monthly_salary: 15000 },
];

describe('searchEmployees', () => {
  it.each([
    ['', 4], ['  ', 4], ['omar', 1], ['OMAR', 1], ['e0000', 4], ['E00002', 1], ['engineering', 2], ['acme', 4],
    ['finance', 1], ['nobody', 0], ['saeed', 1], ['@acme.example', 4],
  ])('query %j finds %i', (query, count) => {
    expect(searchEmployees(people, query)).toHaveLength(count);
  });
});

describe('sortEmployees', () => {
  it.each([
    ['name', false, ['Lina Saeed', 'Maya Costa', 'Omar Haddad', 'Ravi Menon']],
    ['name', true, ['Ravi Menon', 'Omar Haddad', 'Maya Costa', 'Lina Saeed']],
    ['number', false, ['Lina Saeed', 'Ravi Menon', 'Omar Haddad', 'Maya Costa']],
    ['salary', false, ['Maya Costa', 'Omar Haddad', 'Ravi Menon', 'Lina Saeed']],
    ['salary', true, ['Lina Saeed', 'Ravi Menon', 'Omar Haddad', 'Maya Costa']],
  ] as const)('by %s (descending: %s)', (key, descending, names) => {
    expect(sortEmployees(people, key, descending).map((e) => e.full_name)).toEqual(names);
  });

  it('does not mutate its input', () => {
    const copy = [...people];
    sortEmployees(people, 'salary');
    expect(people).toEqual(copy);
  });
});

describe('headcountByDepartment', () => {
  it('counts everyone not terminated', () => {
    expect(headcountByDepartment(people)).toEqual({ Finance: 1, Engineering: 2 });
  });
  it('is empty for no rows', () => {
    expect(headcountByDepartment([])).toEqual({});
  });
});

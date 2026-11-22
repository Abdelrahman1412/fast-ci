import { describe, expect, it } from 'vitest';
import { isValid, validateLeave, type LeaveForm } from './validation';

const good: LeaveForm = { employeeId: '7', leaveType: 'annual', startDate: '2026-11-02', endDate: '2026-11-06', reason: '' };

describe('validateLeave', () => {
  it('accepts a complete form', () => {
    expect(isValid(validateLeave(good))).toBe(true);
  });

  it.each(['', '0', '-1', 'abc', '07', '1.5'])('rejects employee id %j', (employeeId) => {
    expect(validateLeave({ ...good, employeeId }).employeeId).toBeDefined();
  });

  it.each(['annual', 'sick', 'unpaid'])('accepts leave type %s', (leaveType) => {
    expect(validateLeave({ ...good, leaveType }).leaveType).toBeUndefined();
  });

  it.each(['', 'Annual', 'holiday', 'maternity'])('rejects leave type %j', (leaveType) => {
    expect(validateLeave({ ...good, leaveType }).leaveType).toBe('Choose a leave type');
  });

  it.each([
    ['startDate', ''], ['startDate', '2026-02-30'], ['endDate', ''], ['endDate', 'next week'],
  ] as const)('rejects %s %j', (field, value) => {
    expect(validateLeave({ ...good, [field]: value })[field]).toMatch(/valid/);
  });

  it('rejects a reversed range', () => {
    expect(validateLeave({ ...good, startDate: '2026-11-06', endDate: '2026-11-02' }).endDate).toMatch(/before/);
  });

  it.each([
    ['2027-01-31', true],
    ['2027-02-01', false],
  ])('end %s within 90 days: %s', (endDate, ok) => {
    expect(validateLeave({ ...good, endDate }).endDate === undefined).toBe(ok);
  });

  it.each([[500, true], [501, false]])('reason of %i characters valid: %s', (length, ok) => {
    expect(validateLeave({ ...good, reason: 'x'.repeat(length) }).reason === undefined).toBe(ok);
  });
});

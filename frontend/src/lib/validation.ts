import { parseIsoDate } from './dates';

export interface LeaveForm {
  employeeId: string;
  leaveType: string;
  startDate: string;
  endDate: string;
  reason: string;
}

export type Errors = Partial<Record<keyof LeaveForm, string>>;

const TYPES = new Set(['annual', 'sick', 'unpaid']);

export function validateLeave(form: LeaveForm): Errors {
  const errors: Errors = {};
  if (!/^[1-9]\d*$/.test(form.employeeId)) errors.employeeId = 'Choose an employee';
  if (!TYPES.has(form.leaveType)) errors.leaveType = 'Choose a leave type';
  let start: Date | undefined;
  let end: Date | undefined;
  try {
    start = parseIsoDate(form.startDate);
  } catch {
    errors.startDate = 'Enter a valid start date';
  }
  try {
    end = parseIsoDate(form.endDate);
  } catch {
    errors.endDate = 'Enter a valid end date';
  }
  if (start && end) {
    if (end < start) errors.endDate = 'End date is before start date';
    else if ((end.getTime() - start.getTime()) / 86_400_000 > 90) errors.endDate = 'A request cannot exceed 90 days';
  }
  if (form.reason.length > 500) errors.reason = 'Keep the reason under 500 characters';
  return errors;
}

export function isValid(errors: Errors): boolean {
  return Object.keys(errors).length === 0;
}

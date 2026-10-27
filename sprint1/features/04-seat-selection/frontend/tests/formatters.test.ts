import { describe, it, expect } from 'vitest';
import {
  formatCurrency,
  formatShowDateTime,
  formatDuration,
  formatSeatNames,
} from '../features/seat-selection/utils/formatters';

describe('formatters', () => {
  it('formats amounts into Indian Rupees (INR) format', () => {
    const formatted = formatCurrency(400);
    expect(formatted).toContain('400');
    expect(formatted).toContain('₹');
  });

  it('formats show timestamps into Asia/Kolkata timezone', () => {
    // 2026-10-27T08:30:00Z is 14:00 (2:00 PM) in IST (UTC+5:30)
    const { timeStr, fullStr } = formatShowDateTime('2026-10-27T08:30:00Z');
    expect(timeStr).toContain('2:00');
    expect(timeStr).toContain('PM');
    expect(fullStr).toContain('Oct');
  });

  it('formats minutes into human readable duration', () => {
    expect(formatDuration(135)).toBe('2h 15m');
    expect(formatDuration(60)).toBe('1h');
    expect(formatDuration(45)).toBe('45m');
    expect(formatDuration(0)).toBe('0m');
  });

  it('joins seat objects into readable names', () => {
    const seats = [
      { row_label: 'C', seat_number: 5 },
      { row_label: 'C', seat_number: 6 },
    ];
    expect(formatSeatNames(seats)).toBe('C5, C6');
    expect(formatSeatNames([])).toBe('');
  });
});

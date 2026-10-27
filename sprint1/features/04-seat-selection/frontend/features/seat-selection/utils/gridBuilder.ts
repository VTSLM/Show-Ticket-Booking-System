import { SeatItem, GridSeat, GridRow, RowBand, SeatType } from '../types/seat';
import { formatCurrency } from './formatters';

/**
 * Natural row label sorter: 'A' -> 'Z' -> 'AA' -> 'AB'...
 */
export function compareRowLabels(a: string, b: string): number {
  if (a.length !== b.length) {
    return a.length - b.length;
  }
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
}

/**
 * Builds an aligned 2D grid from flat API seats.
 * Gaps in seat_number become aisle spacers ensuring vertical column alignment.
 * Contiguous rows of the same type and price are grouped into labeled tier bands.
 */
export function buildSeatGrid(seats: SeatItem[]): RowBand[] {
  if (!seats || seats.length === 0) {
    return [];
  }

  // 1. Group seats by row_label
  const rowMap = new Map<string, SeatItem[]>();
  let globalMaxSeatNumber = 1;
  let globalMinSeatNumber = 1;

  for (const s of seats) {
    if (!rowMap.has(s.row_label)) {
      rowMap.set(s.row_label, []);
    }
    rowMap.get(s.row_label)!.push(s);

    if (s.seat_number > globalMaxSeatNumber) {
      globalMaxSeatNumber = s.seat_number;
    }
    if (s.seat_number < globalMinSeatNumber) {
      globalMinSeatNumber = s.seat_number;
    }
  }

  // 2. Sort rows in natural cinema order (Row A nearest screen at top)
  const sortedRowLabels = Array.from(rowMap.keys()).sort(compareRowLabels);

  const gridRows: GridRow[] = [];

  for (const rowLabel of sortedRowLabels) {
    const rowSeats = rowMap.get(rowLabel)!;
    // Map seat by seat_number
    const seatByNum = new Map<number, SeatItem>();
    let primaryType: SeatType = 'standard';
    let primaryPrice = 0;

    for (const s of rowSeats) {
      seatByNum.set(s.seat_number, s);
      primaryType = s.seat_type;
      primaryPrice = s.price;
    }

    // Determine row min and max boundaries
    const rowNumbers = rowSeats.map((s) => s.seat_number);
    const rowMin = Math.min(...rowNumbers);
    const rowMax = Math.max(...rowNumbers);

    const builtSeats: GridSeat[] = [];

    // Fill every column position from rowMin to rowMax. Any gap is an aisle spacer.
    for (let num = rowMin; num <= rowMax; num++) {
      const existingSeat = seatByNum.get(num);
      if (existingSeat) {
        builtSeats.push({
          show_seat_id: existingSeat.show_seat_id,
          row_label: existingSeat.row_label,
          seat_number: existingSeat.seat_number,
          seat_type: existingSeat.seat_type,
          price: existingSeat.price,
          status: existingSeat.status,
          is_mine: existingSeat.is_mine,
          is_aisle: false,
        });
      } else {
        // Gap in seat numbers represents an aisle passage
        builtSeats.push({
          show_seat_id: `aisle-${rowLabel}-${num}`,
          row_label: rowLabel,
          seat_number: num,
          seat_type: primaryType,
          price: primaryPrice,
          status: 'reserved',
          is_mine: false,
          is_aisle: true,
        });
      }
    }

    gridRows.push({
      row_label: rowLabel,
      seat_type: primaryType,
      price: primaryPrice,
      seats: builtSeats,
    });
  }

  // 3. Group contiguous rows with identical seat_type and price into visual bands
  const bands: RowBand[] = [];
  let currentBand: RowBand | null = null;

  for (const row of gridRows) {
    if (
      currentBand &&
      currentBand.seat_type === row.seat_type &&
      currentBand.price === row.price
    ) {
      currentBand.rows.push(row);
    } else {
      const typeLabel = row.seat_type.toUpperCase();
      const priceLabel = formatCurrency(row.price);
      currentBand = {
        title: `${typeLabel} — ${priceLabel}`,
        seat_type: row.seat_type,
        price: row.price,
        rows: [row],
      };
      bands.push(currentBand);
    }
  }

  return bands;
}

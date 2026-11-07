/**
 * How this works / why it is safe:
 * Money in LedgerLine is strictly represented as integer paise (1 Rupee = 100 paise).
 * No floating-point math or Decimal approximations are permitted in monetary pathways.
 * This module converts user-entered Rupee strings to exact integer paise at the form boundary,
 * and formats integer paise to formatted INR strings (₹1,00,000.00) using the Indian numbering system.
 */

/**
 * Format integer paise into Indian Rupee display format.
 * E.g., 10000000 -> "₹1,00,000.00"
 */
export function formatPaise(paise: number | bigint): string {
  const p = typeof paise === "bigint" ? Number(paise) : paise;
  const isNegative = p < 0;
  const absPaise = Math.abs(p);
  const rupees = Math.floor(absPaise / 100);
  const remainingPaise = absPaise % 100;

  const formattedRupees = rupees.toLocaleString("en-IN");
  const formattedPaise = remainingPaise.toString().padStart(2, "0");

  return `${isNegative ? "-" : ""}₹${formattedRupees}.${formattedPaise}`;
}

/**
 * Safely parse a Rupee string from a user input form into an exact integer number of paise.
 * Rejects invalid decimals (more than 2 decimal places) and non-numeric inputs.
 * E.g., "1,000.50" -> 100050 paise
 */
export function parseRupeesToPaise(input: string): number | null {
  if (!input) return null;
  const clean = input.replace(/,/g, "").trim();
  if (!clean) return null;

  // Regex strictly matching positive or negative currency with up to 2 decimal places
  const match = clean.match(/^(-)?(\d+)(?:\.(\d{1,2}))?$/);
  if (!match) return null;

  const isNeg = Boolean(match[1]);
  const wholePart = parseInt(match[2] ?? "0", 10);
  const fractionStr = (match[3] ?? "").padEnd(2, "0");
  const fracPart = parseInt(fractionStr, 10);

  if (isNaN(wholePart) || isNaN(fracPart)) return null;

  const totalPaise = wholePart * 100 + fracPart;
  return isNeg ? -totalPaise : totalPaise;
}

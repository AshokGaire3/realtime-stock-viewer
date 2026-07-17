/**
 * Where `price` sits within its [low, high] range, as a 0-100 percentage.
 * A degenerate range (a stablecoin pegged flat, or a provider reporting no
 * spread) has no meaningful position, so it reads as centred.
 */
export const rangePosition = (price: number, low: number, high: number): number => {
  if (!(high > low)) return 50;
  return Math.min(Math.max(((price - low) / (high - low)) * 100, 0), 100);
};

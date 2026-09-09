import { matchesPriceBucket } from "./priceBuckets";

export interface RestaurantFilterCriteria {
  broadcast: string;
  category: string;
  priceBucket: string;
}

export function matchesFilters(
  restaurant: { broadcasts: string[]; category: string | null; reference_price_won: number | null },
  filters: RestaurantFilterCriteria
): boolean {
  if (filters.broadcast && !restaurant.broadcasts.includes(filters.broadcast)) return false;
  if (filters.category && restaurant.category !== filters.category) return false;
  if (!matchesPriceBucket(restaurant.reference_price_won, filters.priceBucket)) return false;
  return true;
}

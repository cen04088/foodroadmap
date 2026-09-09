export interface RestaurantFilterCriteria {
  broadcast: string;
  category: string;
}

export function matchesFilters(
  restaurant: { broadcasts: string[]; category: string | null },
  filters: RestaurantFilterCriteria
): boolean {
  if (filters.broadcast && !restaurant.broadcasts.includes(filters.broadcast)) return false;
  if (filters.category && restaurant.category !== filters.category) return false;
  return true;
}

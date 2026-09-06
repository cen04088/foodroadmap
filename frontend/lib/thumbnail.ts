import type { RestaurantSummary } from "./api";
import { getBroadcastImage } from "./broadcastImages";
import { getYoutubeVideoId } from "./youtube";

export function getRestaurantThumbnailUrl(
  restaurant: Pick<RestaurantSummary, "youtube_url" | "broadcasts">
): string | null {
  const videoId = restaurant.youtube_url ? getYoutubeVideoId(restaurant.youtube_url) : null;
  if (videoId) return `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;

  const primaryBroadcast = restaurant.broadcasts[0] ?? null;
  return primaryBroadcast ? getBroadcastImage(primaryBroadcast) : null;
}

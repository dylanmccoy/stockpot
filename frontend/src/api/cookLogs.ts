// Thin typed wrapper over the HTTP client for /api/cook-logs (adapter — R-2).

import { client } from "./client";
import type { CookLogList, CookLogRead } from "../types";

export interface CookLogsQuery {
  limit?: number; // 1..200, default 50
  offset?: number; // >= 0, default 0
}

export const cookLogsApi = {
  list: (query: CookLogsQuery = {}, signal?: AbortSignal) => {
    const params = new URLSearchParams();
    if (query.limit !== undefined) params.set("limit", String(query.limit));
    if (query.offset !== undefined) params.set("offset", String(query.offset));
    const qs = params.toString();
    return client.get<CookLogList>(
      qs ? `/cook-logs?${qs}` : "/cook-logs",
      signal,
    );
  },
  get: (logId: number, signal?: AbortSignal) =>
    client.get<CookLogRead>(`/cook-logs/${logId}`, signal),

  // Per-recipe history feed (spec §10.8): unpaginated, `cooked_at DESC, id DESC`
  // from the server. Backs the `["recipe-cook-logs", id]` query in RecipeDetail.
  byRecipe: (recipeId: number, signal?: AbortSignal) =>
    client.get<CookLogRead[]>(`/recipes/${recipeId}/cook-logs`, signal),
};

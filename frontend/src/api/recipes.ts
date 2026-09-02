// Thin typed wrapper over the HTTP client for /api/recipes.
//
// Availability and cook are math-DTO screens (R-2): keep their callers behind
// this adapter so a late backend DTO change is a one-file edit here.

import { client } from "./client";
import type {
  AvailabilityReport,
  CookLogRead,
  CookRequest,
  RecipeCreate,
  RecipeRead,
  RecipeUpdate,
} from "../types";

export const recipesApi = {
  list: (signal?: AbortSignal) => client.get<RecipeRead[]>("/recipes", signal),
  get: (id: number, signal?: AbortSignal) =>
    client.get<RecipeRead>(`/recipes/${id}`, signal),
  create: (body: RecipeCreate) => client.post<RecipeRead>("/recipes", body),
  update: (id: number, body: RecipeUpdate) =>
    client.put<RecipeRead>(`/recipes/${id}`, body),
  remove: (id: number) => client.del<void>(`/recipes/${id}`),

  availability: (id: number, multiplier: number, signal?: AbortSignal) =>
    client.get<AvailabilityReport>(
      `/recipes/${id}/availability?multiplier=${encodeURIComponent(multiplier)}`,
      signal,
    ),

  cook: (id: number, body: CookRequest) =>
    client.post<CookLogRead>(`/recipes/${id}/cook`, body),

  cookLogs: (id: number, signal?: AbortSignal) =>
    client.get<CookLogRead[]>(`/recipes/${id}/cook-logs`, signal),
};

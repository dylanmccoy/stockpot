// Thin typed wrapper over the HTTP client for /api/grocery (adapter — R-2).

import { client } from "./client";
import type {
  GroceryListCreate,
  GroceryListItemIn,
  GroceryListItemRead,
  GroceryListItemUpdate,
  GroceryListRead,
  GroceryListStatus,
} from "../types";

export const groceryApi = {
  list: (status?: GroceryListStatus, signal?: AbortSignal) =>
    client.get<GroceryListRead[]>(
      status ? `/grocery?status=${status}` : "/grocery",
      signal,
    ),
  get: (id: number, signal?: AbortSignal) =>
    client.get<GroceryListRead>(`/grocery/${id}`, signal),
  create: (body: GroceryListCreate) =>
    client.post<GroceryListRead>("/grocery", body),
  remove: (id: number) => client.del<void>(`/grocery/${id}`),

  addItem: (id: number, body: GroceryListItemIn) =>
    client.post<GroceryListItemRead>(`/grocery/${id}/items`, body),
  updateItem: (id: number, itemId: number, body: GroceryListItemUpdate) =>
    client.patch<GroceryListItemRead>(`/grocery/${id}/items/${itemId}`, body),
  removeItem: (id: number, itemId: number) =>
    client.del<void>(`/grocery/${id}/items/${itemId}`),

  submit: (id: number) => client.post<GroceryListRead>(`/grocery/${id}/submit`),
  archive: (id: number) =>
    client.post<GroceryListRead>(`/grocery/${id}/archive`),
};

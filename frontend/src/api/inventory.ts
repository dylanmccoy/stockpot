// Thin typed wrapper over the HTTP client for /api/inventory (adapter — R-2).

import { client } from "./client";
import type {
  InventoryItemCreate,
  InventoryItemRead,
  InventoryItemUpdate,
} from "../types";

export const inventoryApi = {
  list: (signal?: AbortSignal) =>
    client.get<InventoryItemRead[]>("/inventory", signal),
  create: (body: InventoryItemCreate) =>
    client.post<InventoryItemRead>("/inventory", body),
  update: (id: number, body: InventoryItemUpdate) =>
    client.patch<InventoryItemRead>(`/inventory/${id}`, body),
  remove: (id: number) => client.del<void>(`/inventory/${id}`),
};

// Thin typed wrapper over the HTTP client for /api/auth.

import { client } from "./client";
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserRead,
} from "../types";

export const authApi = {
  register: (body: RegisterRequest) =>
    client.post<TokenResponse>("/auth/register", body),
  login: (body: LoginRequest) =>
    client.post<TokenResponse>("/auth/login", body),
  logout: () => client.post<void>("/auth/logout"),
  me: () => client.get<UserRead>("/auth/me"),
};

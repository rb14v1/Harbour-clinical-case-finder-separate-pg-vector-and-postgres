import { apiClient } from "./client";
import type { User } from "../types";

export function login(email: string, password: string) {
  return apiClient.post<{ access: string; refresh: string }>("/auth/login/", { email, password });
}

export function register(data: {
  email: string;
  password: string;
  full_name?: string;
  specialty?: string;
}) {
  return apiClient.post<User>("/auth/register/", data);
}

// The refresh token is sent by the browser as an HttpOnly cookie.
export function logout() {
  return apiClient.post("/auth/logout/", {});
}

export function fetchMe() {
  return apiClient.get<User>("/auth/me/");
}

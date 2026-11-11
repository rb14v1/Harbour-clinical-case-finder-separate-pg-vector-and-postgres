import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

// Entra ID sign-in entry point on the backend (mozilla-django-oidc).
const OIDC_LOGIN_URL =
  import.meta.env.VITE_OIDC_LOGIN_URL || `${API_BASE_URL.replace(/\/api\/?$/, "")}/oidc/authenticate/`;

// Access token lives only in memory (module-level variable), never
// localStorage, to limit XSS blast radius. The refresh token is never
// visible to JavaScript: the backend keeps it in an HttpOnly, Secure,
// SameSite cookie scoped to /api/auth/, which the browser sends along with
// credentialed requests.
let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export function redirectToIdentityProvider() {
  window.location.assign(OIDC_LOGIN_URL);
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

// Obtains a fresh access token from the HttpOnly refresh cookie, or - right
// after an Entra ID sign-in - from the backend's server-side OIDC session.
export async function refreshAccessToken(): Promise<string | null> {
  try {
    const response = await axios.post(`${API_BASE_URL}/auth/refresh/`, {}, { withCredentials: true });
    const newAccess = response.data.access as string;
    setAccessToken(newAccess);
    return newAccess;
  } catch {
    try {
      const response = await axios.get(`${API_BASE_URL}/auth/oidc/token/`, { withCredentials: true });
      const newAccess = response.data.access as string;
      setAccessToken(newAccess);
      return newAccess;
    } catch {
      setAccessToken(null);
      return null;
    }
  }
}

const CREDENTIAL_ENDPOINTS = ["/auth/login/", "/auth/register/"];

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetriableConfig | undefined;

    const isCredentialRequest = CREDENTIAL_ENDPOINTS.some((path) => originalRequest?.url?.includes(path));

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry && !isCredentialRequest) {
      originalRequest._retry = true;

      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }
      const newToken = await refreshPromise;

      if (newToken) {
        originalRequest.headers = originalRequest.headers ?? {};
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      }

      // Unauthenticated: send the browser to the identity provider.
      redirectToIdentityProvider();
    }

    return Promise.reject(error);
  }
);

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (data?.detail) return String(data.detail);
    if (data) return JSON.stringify(data);
    return error.message;
  }
  return String(error);
}

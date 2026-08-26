/**
 * MedGraphRAG Frontend — API HTTP Client
 * Enforces contract-first requests, Bearer token injection, 401 redirects & 403 handling.
 */

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
export const API_BASE_URL = API_BASE;
export const API_PREFIX = '/api/v1';

export class ApiRequestError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.data = data;
  }
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = sessionStorage.getItem('medgraph_token');
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Set default JSON Content-Type only if not sending FormData
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  // Ensure path starts with /api/v1
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const fullUrl = `${API_BASE}${cleanEndpoint.startsWith(API_PREFIX) ? cleanEndpoint : `${API_PREFIX}${cleanEndpoint}`}`;

  try {
    const response = await fetch(fullUrl, {
      ...options,
      headers,
    });

    // 1. Handle 401 Unauthorized: Clear session and notify app
    if (response.status === 401) {
      sessionStorage.removeItem('medgraph_token');
      sessionStorage.removeItem('medgraph_user');
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
      throw new ApiRequestError(401, 'Session expired or invalid credentials. Please log in again.');
    }

    // 2. Handle HTTP Errors (400, 403, 413, 415, 422, 500)
    if (!response.ok) {
      let errorBody: any = null;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = await response.text();
      }

      let errorMsg = 'An unexpected server error occurred.';
      if (typeof errorBody === 'object' && errorBody !== null) {
        if (typeof errorBody.detail === 'string') {
          errorMsg = errorBody.detail;
        } else if (typeof errorBody.detail === 'object' && errorBody.detail?.detail) {
          errorMsg = errorBody.detail.detail;
        } else if (errorBody.error) {
          errorMsg = errorBody.error;
        }
      } else if (typeof errorBody === 'string' && errorBody.trim()) {
        errorMsg = errorBody;
      }

      throw new ApiRequestError(response.status, errorMsg, errorBody);
    }

    // 3. Return JSON payload
    return (await response.json()) as T;
  } catch (error: any) {
    if (error instanceof ApiRequestError) {
      throw error;
    }
    // Network / offline connection failure
    throw new ApiRequestError(
      0,
      'Unable to reach the MedGraphRAG backend server. Please verify the service is running.'
    );
  }
}

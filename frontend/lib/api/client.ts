// API client with X-Request-ID and error handling

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export class APIError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public requestId?: string
  ) {
    super(`API Error ${status}: ${detail}`);
    this.name = 'APIError';
  }
}

function generateRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
}

export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const requestId = generateRequestId();
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

  const headers = new Headers(options?.headers);
  headers.set('X-Request-ID', requestId);
  headers.set('Content-Type', 'application/json');

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let detail = `HTTP ${response.status} ${response.statusText}`;
      try {
        const errorData = await response.json();
        detail = errorData.detail || detail;
      } catch {
        // Failed to parse error JSON, use status text
      }

      throw new APIError(response.status, detail, requestId);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return await response.json();
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }

    // Network error or other fetch failure
    throw new APIError(
      0,
      error instanceof Error ? error.message : 'Network request failed',
      requestId
    );
  }
}

// Helper for building query strings
export function buildQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const searchParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value));
    }
  });

  const qs = searchParams.toString();
  return qs ? `?${qs}` : '';
}

import type { ApiError, SalonDetails, SalonListItem, SalonUpdateRequest } from '../types/salon'

const DEFAULT_API_BASE = 'http://localhost:8080/api'

function getApiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim()
  const base = configured || DEFAULT_API_BASE
  return base.replace(/\/$/, '')
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBase()}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
    ...options,
  })

  if (!response.ok) {
    let message = response.statusText
    try {
      const body = (await response.json()) as ApiError
      message = body.message ?? message
    } catch {
      // ignore parse errors
    }
    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export function getSalons(district?: string, service?: string): Promise<SalonListItem[]> {
  const params = new URLSearchParams()
  if (district) params.set('district', district)
  if (service) params.set('service', service)
  const query = params.toString()
  return request<SalonListItem[]>(`/salons${query ? `?${query}` : ''}`)
}

export function getSalon(id: number): Promise<SalonDetails> {
  return request<SalonDetails>(`/salons/${id}`)
}

export function updateSalon(id: number, body: SalonUpdateRequest): Promise<SalonDetails> {
  return request<SalonDetails>(`/salons/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

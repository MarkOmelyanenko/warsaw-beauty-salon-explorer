export interface SalonListItem {
  id: number
  name: string
  district: string
  rating: number | null
  reviewCount: number | null
  priceRange: string | null
}

export interface SalonDetails {
  id: number
  name: string
  address: string
  district: string
  phone: string | null
  websiteUrl: string | null
  services: string[]
  priceRange: string | null
  rating: number | null
  reviewCount: number | null
  source: string | null
  externalId: string | null
  createdAt: string
  updatedAt: string
}

export interface SalonUpdateRequest {
  name?: string | null
  address?: string | null
  district?: string | null
  phone?: string | null
  websiteUrl?: string | null
  services?: string[] | null
  priceRange?: string | null
  rating?: number | null
  reviewCount?: number | null
}

export interface ApiError {
  status: number
  message: string
}

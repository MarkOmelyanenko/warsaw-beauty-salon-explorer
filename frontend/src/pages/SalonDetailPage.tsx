import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { listReturnTo } from '../utils/listNavigation'
import { getSalon, updateSalon } from '../api/salons'
import { WARSAW_DISTRICTS } from '../constants/filters'
import type { SalonDetails } from '../types/salon'

const PHONE_INPUT_PATTERN = '[\\d+\\s\\-()]+'

function sanitizePhoneInput(value: string): string {
  return value.replace(/[^\d+\s\-()]/g, '')
}

function populateForm(salon: SalonDetails) {
  return {
    name: salon.name,
    address: salon.address,
    district: salon.district,
    phone: sanitizePhoneInput(salon.phone ?? ''),
    websiteUrl: salon.websiteUrl ?? '',
    servicesText: salon.services.join(', '),
    priceRange: salon.priceRange ?? '',
    rating: salon.rating != null ? String(salon.rating) : '',
    reviewCount: salon.reviewCount != null ? String(salon.reviewCount) : '',
  }
}

function getRatingStarFill(rating: number | null): string | null {
  if (rating == null) {
    return null
  }

  const clampedRating = Math.max(0, Math.min(5, rating))
  return `${(clampedRating / 5) * 100}%`
}

export default function SalonDetailPage() {
  const { id } = useParams()
  const location = useLocation()
  const salonId = Number(id)
  const listTo = listReturnTo(location.state)

  const [salon, setSalon] = useState<SalonDetails | null>(null)
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [district, setDistrict] = useState('')
  const [phone, setPhone] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [servicesText, setServicesText] = useState('')
  const [priceRange, setPriceRange] = useState('')
  const [rating, setRating] = useState('')
  const [reviewCount, setReviewCount] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!Number.isFinite(salonId)) {
      setError('Invalid salon id')
      setLoading(false)
      return
    }

    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await getSalon(salonId)
        if (!cancelled) {
          setSalon(data)
          const form = populateForm(data)
          setName(form.name)
          setAddress(form.address)
          setDistrict(form.district)
          setPhone(form.phone)
          setWebsiteUrl(form.websiteUrl)
          setServicesText(form.servicesText)
          setPriceRange(form.priceRange)
          setRating(form.rating)
          setReviewCount(form.reviewCount)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load salon')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [salonId])

  function startEditing() {
    if (!salon) {
      return
    }
    const form = populateForm(salon)
    setName(form.name)
    setAddress(form.address)
    setDistrict(form.district)
    setPhone(form.phone)
    setWebsiteUrl(form.websiteUrl)
    setServicesText(form.servicesText)
    setPriceRange(form.priceRange)
    setRating(form.rating)
    setReviewCount(form.reviewCount)
    setError(null)
    setEditing(true)
  }

  function cancelEditing() {
    if (salon) {
      const form = populateForm(salon)
      setName(form.name)
      setAddress(form.address)
      setDistrict(form.district)
      setPhone(form.phone)
      setWebsiteUrl(form.websiteUrl)
      setServicesText(form.servicesText)
      setPriceRange(form.priceRange)
      setRating(form.rating)
      setReviewCount(form.reviewCount)
    }
    setError(null)
    setEditing(false)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!salon) {
      return
    }

    setSaving(true)
    setError(null)

    const services = servicesText
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)

    try {
      const updated = await updateSalon(salon.id, {
        name,
        address,
        district,
        phone: phone.trim() || null,
        websiteUrl: websiteUrl || null,
        services,
        priceRange: priceRange || null,
        rating: rating ? Number(rating) : null,
        reviewCount: reviewCount ? Number(reviewCount) : null,
      })
      setSalon(updated)
      setEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update salon')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <p className="status">Loading salon...</p>
  }

  if (error && !salon) {
    return (
      <div className="page">
        <p className="status error">{error}</p>
        <Link to={listTo}>Back to list</Link>
      </div>
    )
  }

  if (!salon) {
    return (
      <div className="page">
        <p className="status error">Salon not found</p>
        <Link to={listTo}>Back to list</Link>
      </div>
    )
  }

  const ratingStarFill = getRatingStarFill(salon.rating)

  return (
    <div className="page">
      <p>
        <Link to={listTo}>← Back to list</Link>
      </p>

      <header className="page-header">
        <h1>{salon.name}</h1>
        <p className="muted">{salon.district}</p>
      </header>

      {editing ? (
        <form className="edit-form" onSubmit={handleSubmit}>
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label>
            Address
            <input value={address} onChange={(event) => setAddress(event.target.value)} required />
          </label>
          <label>
            District
            <select value={district} onChange={(event) => setDistrict(event.target.value)} required>
              {WARSAW_DISTRICTS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Phone
            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              pattern={PHONE_INPUT_PATTERN}
              title="Only digits, spaces, +, -, and parentheses"
              value={phone}
              onChange={(event) => setPhone(sanitizePhoneInput(event.target.value))}
            />
          </label>
          <label>
            Website URL
            <input value={websiteUrl} onChange={(event) => setWebsiteUrl(event.target.value)} />
          </label>
          <label>
            Services (comma-separated)
            <input value={servicesText} onChange={(event) => setServicesText(event.target.value)} />
          </label>
          <label>
            Price range
            <input value={priceRange} onChange={(event) => setPriceRange(event.target.value)} />
          </label>
          <label>
            Rating
            <input
              type="number"
              min="0"
              max="5"
              step="0.01"
              value={rating}
              onChange={(event) => setRating(event.target.value)}
            />
          </label>
          <label>
            Review count
            <input
              type="number"
              min="0"
              value={reviewCount}
              onChange={(event) => setReviewCount(event.target.value)}
            />
          </label>

          {error && <p className="status error">{error}</p>}

          <div className="form-actions">
            <button className="button" type="submit" disabled={saving}>
              {saving ? 'Saving...' : 'Save changes'}
            </button>
            <button className="button secondary" type="button" onClick={cancelEditing} disabled={saving}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <>
          <dl className="details">
            <dt>Address</dt>
            <dd>{salon.address}</dd>
            <dt>Phone</dt>
            <dd>{salon.phone ?? 'No phone available'}</dd>
            <dt>Website</dt>
            <dd>
              {salon.websiteUrl ? (
                <a href={salon.websiteUrl} target="_blank" rel="noreferrer">
                  {salon.websiteUrl}
                </a>
              ) : (
                'No website available'
              )}
            </dd>
            <dt>Services</dt>
            <dd>{salon.services.length > 0 ? salon.services.join(', ') : 'No services listed'}</dd>
            <dt>Price range</dt>
            <dd>{salon.priceRange ?? '—'}</dd>
            <dt>Rating</dt>
            <dd>
              <span className="rating-summary">
                {ratingStarFill && (
                  <span className="rating-stars" aria-label={`${salon.rating} out of 5 stars`}>
                    <span className="rating-stars-empty" aria-hidden="true">
                      ★★★★★
                    </span>
                    <span className="rating-stars-filled" aria-hidden="true" style={{ width: ratingStarFill }}>
                      ★★★★★
                    </span>
                  </span>
                )}
                <span>
                  {salon.rating != null ? salon.rating : '—'}
                  {salon.reviewCount != null ? ` (${salon.reviewCount} reviews)` : ''}
                </span>
              </span>
            </dd>
          </dl>

          <button className="button" type="button" onClick={startEditing}>
            Edit salon
          </button>
        </>
      )}
    </div>
  )
}

import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getSalons } from "../api/salons";
import { WARSAW_DISTRICTS } from "../constants/filters";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import type { SalonListItem } from "../types/salon";
import { listLinkState } from "../utils/listNavigation";

const SERVICE_DEBOUNCE_MS = 300;

function formatRating(rating: number | null): string {
  return rating != null ? String(rating) : "No rating";
}

function formatReviewCount(count: number | null): string {
  return count != null ? String(count) : "—";
}

function formatPriceRange(priceRange: string | null): string {
  return priceRange ?? "—";
}

function parseDistrictParam(value: string | null): string {
  if (!value) {
    return "";
  }
  return (WARSAW_DISTRICTS as readonly string[]).includes(value) ? value : "";
}

function syncServiceSearchParam(
  prev: URLSearchParams,
  service: string,
): URLSearchParams {
  const next = new URLSearchParams(prev);
  const current = next.get("service") ?? "";
  if (service === current) {
    return prev;
  }
  if (service) {
    next.set("service", service);
  } else {
    next.delete("service");
  }
  return next;
}

export default function SalonListPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const district = parseDistrictParam(searchParams.get("district"));
  const serviceFromUrl = searchParams.get("service") ?? "";

  const [serviceInput, setServiceInput] = useState(serviceFromUrl);
  const debouncedService = useDebouncedValue(serviceInput, SERVICE_DEBOUNCE_MS);

  const committedServiceRef = useRef(serviceFromUrl);

  const [salons, setSalons] = useState<SalonListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (serviceFromUrl === committedServiceRef.current) {
      return;
    }
    committedServiceRef.current = serviceFromUrl;
    setServiceInput(serviceFromUrl);
  }, [serviceFromUrl]);

  useEffect(() => {
    committedServiceRef.current = debouncedService;
    setSearchParams(
      (prev) => syncServiceSearchParam(prev, debouncedService),
      { replace: true },
    );
  }, [debouncedService, setSearchParams]);

  function handleDistrictChange(value: string) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) {
          next.set("district", value);
        } else {
          next.delete("district");
        }
        return next;
      },
      { replace: true },
    );
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getSalons(
          district || undefined,
          debouncedService || undefined,
        );
        if (!cancelled) {
          setSalons(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load salons",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [district, debouncedService]);

  return (
    <div className="page">
      <header className="page-header">
        <h1>Warsaw Salon Explorer</h1>
        <p>Browse salons across Warsaw districts</p>
      </header>

      <section className="filters">
        <label>
          District
          <select
            value={district}
            onChange={(event) => handleDistrictChange(event.target.value)}
          >
            <option value="">All districts</option>
            {WARSAW_DISTRICTS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <label>
          Service
          <input
            type="text"
            value={serviceInput}
            onChange={(event) => setServiceInput(event.target.value)}
            placeholder="Type service name"
          />
        </label>
      </section>

      {loading && <p className="status">Loading salons...</p>}
      {error && <p className="status error">{error}</p>}

      {!loading && !error && salons.length === 0 && (
        <p className="status">
          No salons found. Import data with the collection script or add seed
          data.
        </p>
      )}

      {!loading && !error && salons.length > 0 && (
        <div className="table-wrap">
          <table className="salon-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>District</th>
                <th>Rating</th>
                <th>Reviews</th>
                <th>Price</th>
              </tr>
            </thead>
            <tbody>
              {salons.map((salon) => (
                <tr key={salon.id}>
                  <td>
                    <Link
                      className="salon-link"
                      to={`/salons/${salon.id}`}
                      state={listLinkState(searchParams)}
                    >
                      {salon.name}
                    </Link>
                  </td>
                  <td>{salon.district}</td>
                  <td>{formatRating(salon.rating)}</td>
                  <td>{formatReviewCount(salon.reviewCount)}</td>
                  <td>{formatPriceRange(salon.priceRange)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

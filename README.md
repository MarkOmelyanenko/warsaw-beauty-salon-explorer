# Warsaw Beauty Salon Explorer

## 1. Project overview

A local services marketplace foundation for Warsaw beauty salons: browse salons by district and service, view details (contact, ratings, price ranges, service list), and edit records via a simple web UI. The app ships with seed data collected from public Booksy listings (enriched optionally with Google Places for phone numbers), served by a Spring Boot API and a React frontend.

```
Booksy (+ Google)  →  salons_clean.json  →  PostgreSQL (seed on startup)  →  REST API (Spring Boot)  →  React UI
```

## 2. Tech stack

| Layer               | Technologies                                                                         |
| ------------------- | ------------------------------------------------------------------------------------ |
| **Backend**         | Java 21, Spring Boot 4, Spring Data JPA, PostgreSQL 16, Flyway migrations            |
| **Frontend**        | React 19, TypeScript, Vite 8                                                         |
| **Data collection** | Python 3 (`data/collect_salons_v2.py`), Booksy public pages, Google Places API (New) |

**Data sources**

- **Booksy (primary)** — Warsaw salon listings with service menus and PLN price hints on public business pages. Chosen because it is the dominant booking platform for Polish beauty businesses and exposes the fields the product needs (services, price ranges, ratings) in one place.
- **Google Places API (secondary)** — Text search + place details used only to fill missing phone numbers and store a `place_id` as `externalId`. Not used as the primary catalog because it does not provide Booksy-style service/price detail and would increase API cost and quota usage for bulk collection.

## 3. How to run the application

### Prerequisites

- **Docker path:** Docker and Docker Compose
- **Local path:** Java 21, Node.js 22+, npm, PostgreSQL 16 (or run only Postgres via Docker), Python 3.10+ for data collection

### Environment setup

All services share one root `.env` file (gitignored). Copy the template and adjust placeholders:

```bash
cp .env.example .env
```

Example `.env` (no real secrets):

```env
# PostgreSQL (Docker postgres service + local JDBC)
POSTGRES_DB=salons_db
POSTGRES_USER=salons_user
POSTGRES_PASSWORD=change_me_postgres

SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/salons_db
SPRING_DATASOURCE_USERNAME=salons_user
SPRING_DATASOURCE_PASSWORD=change_me_postgres
APP_CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Frontend (Vite dev + Docker build arg)
VITE_API_BASE_URL=http://localhost:8080/api

# Optional — phone enrichment in data/collect_salons_v2.py
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here
```

| Variable                   | Used by                                         |
| -------------------------- | ----------------------------------------------- |
| `POSTGRES_*`               | Docker Postgres service                         |
| `SPRING_DATASOURCE_*`      | Spring Boot (`backend/`)                        |
| `APP_CORS_ALLOWED_ORIGINS` | Backend CORS (comma-separated origins)          |
| `VITE_API_BASE_URL`        | Vite dev server and frontend Docker image build |
| `GOOGLE_PLACES_API_KEY`    | Data collector only (optional)                  |

When running the backend **inside Docker Compose**, the DB host is overridden to `postgres` automatically. When running **`./mvnw spring-boot:run` locally**, keep `localhost` in `SPRING_DATASOURCE_URL`.

---

### Option A — With Docker (full stack)

From the project root:

```bash
docker compose up --build
```

| Service     | URL                              |
| ----------- | -------------------------------- |
| Frontend    | http://localhost:3000            |
| Backend API | http://localhost:8080/api/salons |
| PostgreSQL  | `localhost:5432`                 |

The frontend image is built with `VITE_API_BASE_URL` from `.env`, so the browser calls the backend on port 8080 directly (CORS is enabled on the API).

To reset the database and re-import seed JSON:

```bash
docker compose down -v
docker compose up --build
```

---

### Option B — Without Docker (local development)

**1. PostgreSQL**

Either install PostgreSQL locally and create a database/user matching `.env`, or start only Postgres in Docker:

```bash
docker compose up postgres -d
```

**2. Backend**

```bash
cd backend
./mvnw spring-boot:run
```

On first start with an empty database, Flyway runs migrations and `DataSeeder` imports `classpath:data/salons_clean.json`.

**3. Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 (Vite loads `VITE_*` from the repo-root `.env` via `envDir: '..'`).

**Listing filters (frontend URL)**

On the home page, district and service filters are reflected in the browser URL so you can bookmark or share a view. District updates the query string immediately; the service field waits **300 ms** after you stop typing before updating the URL and refetching (fewer API calls while typing).

| Query param | Example    | Notes                                       |
| ----------- | ---------- | ------------------------------------------- |
| `district`  | `Mokotów`  | Must match a Warsaw district name in the UI |
| `service`   | `manicure` | Substring match on salon services (API)     |

Example: `http://localhost:5173/?district=Mokotów&service=manicure` (Docker frontend uses port **3000** with the same path and params).

**4. Data collection (optional — refresh seed file)**

```bash
cd data
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install requests certifi
python collect_salons_v2.py
```

The script writes `data/salons_clean.json` and copies to `backend/src/main/resources/data/salons_clean.json`. Restart the backend with an **empty** `salons` table to load the new file (truncate tables or recreate the database).

---

### API (quick reference)

| Method  | Path               | Description                                                                   |
| ------- | ------------------ | ----------------------------------------------------------------------------- |
| `GET`   | `/api/salons`      | List salons (`?district=`, `?service=`); same params on the frontend home URL |
| `GET`   | `/api/salons/{id}` | Salon details                                                                 |
| `PATCH` | `/api/salons/{id}` | Partial update (no auth in MVP)                                               |

## 4. Technical decisions worth mentioning

### Booksy-first architecture

Salons are discovered and parsed from Booksy category search pages (hair, barber, nails, cosmetics, brows/lashes, massage) for Warsaw.

Google Places is **not** the primary source because it is weak for structured beauty service menus and PLN price bands, and bulk place search/detail calls are costlier.

### District detection

District is inferred from the Booksy **address** string: the address is Unicode-normalized (strip diacritics for matching), then scanned against the 18 official Warsaw district names, **longest name first** (so e.g. `Praga-Południe` wins over shorter substrings). Salons whose address does not contain a recognized district are skipped.

### Missing fields and fallbacks

Parsing prefers **JSON-LD** embedded in Booksy HTML, then **regex fallbacks** on raw HTML for name, address, rating, and review count. Empty or missing scalar fields are stored as `"Not available"` (or `0` for numeric ratings/counts when absent). **Google Places** optionally replaces `"Not available"` phones via name + `Warszawa` text search; if `GOOGLE_PLACES_API_KEY` is unset, collection continues without phone enrichment. Salons **without at least one service** are not added to the dataset.

### Deduplication

- **URL level:** each Booksy business URL is processed once per run (`seen_urls`).
- **Record level:** `normalized(name)|normalized(address)` merge keys prevent duplicate salons across categories (`seen_merge_keys` during collection; again when serializing JSON).
- **Diversity:** at most **two salons per Booksy category per district** so the sample is not dominated by a single category.

Default collection target is **7 salons per district** (18 districts → up to 126 records), configurable via `--target-per-district`.

## 5. What I'd improve with more time

- **Service name normalization** — Map Polish labels (e.g. `Strzyżenie damskie`) to canonical categories (`haircut`, `nails`) for consistent filters and search.
- **Pagination on the listing page** — The API returns the full list; the UI would benefit from server-side paging and sort options as the catalog grows.
- **Authentication on `PATCH /api/salons/{id}`** — Protect edits (e.g. API key or JWT) so public clients cannot modify data.
- **Automated tests and CI** — JUnit/Mockito for the API, frontend component tests, and a pipeline running `mvn test` + `npm run build` on every push.
- **Persisted enrichment cache** — Store Google `place_id` / phone lookups locally to avoid repeat billing on re-runs.
- **User reviews display** — Show individual customer reviews on the salon detail page, not just the aggregate count.
- **Map view** — Display salons on an interactive map (e.g. Leaflet + OpenStreetMap) with pins per district. Would require geocoding addresses to coordinates — either via Google Geocoding API or Nominatim (free, no quota).
- **Salon photos** — Booksy business pages include cover and gallery images. Storing photo URLs and displaying them on the detail page would significantly improve the browsing experience.
- **Search by name** — Allow users to search salons by business name directly from the listing page, in addition to the existing district and service filters.

## 6. **Nationwide coverage (all of Poland)**

The current scraper targets Warsaw by using Booksy's city-scoped URLs (`/3_warszawa`). Extending to all of Poland would require the
following steps:

1. **City list** — Compile a list of Polish cities and their Booksy city slugs. Booksy covers most major and mid-size Polish cities, so slug discovery could be automated by scraping the Booksy sitemap.

2. **Booksy categories** - Extend Booksy category URLs beyond Warsaw, add more `BOOKSY_CATEGORIES`, tune `--max-pages` / workers, and cache business pages between runs to scale the scraper without re-fetching unchanged salons.

3. **Parallel city scraping** — Run one scraper worker per city using
   `concurrent.futures.ProcessPoolExecutor` (CPU-bound) or a task queue like Celery +
   Redis to distribute work across multiple machines.

4. **Incremental updates** — Instead of re-scraping everything from scratch, store each
   salon's Booksy URL and a `last_scraped_at` timestamp. On subsequent runs, only revisit
   pages that haven't been refreshed within a configurable TTL (e.g. 7 days). This reduces
   load on Booksy and keeps costs low.

5. **Respectful scraping** — At Poland scale, request volume increases significantly.
   Introduce per-domain rate limiting, randomized delays, and rotating User-Agent headers
   to avoid being blocked. In production, consider negotiating a data partnership with
   Booksy or switching to an official API if one becomes available.

6. **Database** — Replace the flat JSON seed file with a proper pipeline: scraped records
   → staging table → deduplication → production table. PostgreSQL's `ON CONFLICT DO UPDATE`
   (upsert by Booksy URL) handles deduplication cleanly at scale.

7. **Infrastructure** — For full Poland coverage (~500+ cities, tens of thousands of
   salons), the scraper would run as a scheduled job (e.g. GitHub Actions cron or a
   Kubernetes CronJob) writing directly to the production database, rather than generating
   a static JSON file.
8. **Self-registration** — Allow salon owners to register and manage their own listings
   directly in the platform. This shifts data maintenance from scraping to the businesses
   themselves, which improves data accuracy and freshness. Would require an owner-facing
   UI (claim/create a listing, edit details, upload photos), authentication, and a
   moderation layer to prevent spam or fake listings. This is the model used by Booksy,
   Google Business Profile, and most mature local services marketplaces.

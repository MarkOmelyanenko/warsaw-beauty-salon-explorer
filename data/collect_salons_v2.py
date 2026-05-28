#!/usr/bin/env python3
"""Collect Warsaw salon seed data (Booksy-first, Google phone fallback)."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import ssl
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import unescape
from pathlib import Path
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:
    certifi = None


LOGGER = logging.getLogger("collect_salons_v2")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
LOCAL_OUTPUT_PATH = SCRIPT_DIR / "salons_clean.json"
BACKEND_OUTPUT_PATH = PROJECT_ROOT / "backend" / "src" / "main" / "resources" / "data" / "salons_clean.json"
DEFAULT_OUTPUT_PATH = LOCAL_OUTPUT_PATH
BOOKSY_BASE_URL = "https://booksy.com"
GOOGLE_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

WARSAW_DISTRICTS = [
    "Bemowo",
    "Białołęka",
    "Bielany",
    "Mokotów",
    "Ochota",
    "Praga-Południe",
    "Praga-Północ",
    "Rembertów",
    "Śródmieście",
    "Targówek",
    "Ursus",
    "Ursynów",
    "Wawer",
    "Wesoła",
    "Wilanów",
    "Włochy",
    "Wola",
    "Żoliborz",
]

BOOKSY_CATEGORIES = [
    "fryzjer",
    "barber-shop",
    "salon-kosmetyczny",
    "paznokcie",
    "brwi-i-rzesy",
    "masaz",
]

BOOKSY_CATEGORY_SEARCH_URL = "https://booksy.com/pl-pl/s/{category}/3_warszawa?businessesPage={page}"

BOOKSY_EXCLUDED_SERVICE_WORDS = {
    "booksy",
    "warszawa",
    "poland",
    "opinie",
    "reviews",
    "zarezerwuj",
    "rezerwuj",
    "kontakt",
    "login",
    "sign in",
    "mapa",
    "strona",
    "website",
}


@dataclass
class BooksySalon:
    name: str
    address: str
    district: str
    phone: str
    website_url: str
    services: list[str]
    price_range: str
    rating: float
    review_count: int
    external_id: str = ""


def load_dotenv(paths: list[Path]) -> None:
    """Load simple KEY=VALUE pairs without requiring python-dotenv."""
    for path in paths:
        if not path.exists():
            continue

        LOGGER.debug("Loading environment variables from %s", path)
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if not key:
                LOGGER.warning("Ignoring malformed .env line %s in %s", line_number, path)
                continue

            os.environ.setdefault(key, value)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def decimal_from_value(value: Any, default: str = "0.0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        LOGGER.debug("Could not parse decimal value %r, using %s", value, default)
        return Decimal(default)


def format_price_range(values: list[Decimal]) -> str:
    valid = sorted({value.quantize(Decimal("1"), rounding=ROUND_HALF_UP) for value in values if value > 0})
    if not valid:
        return ""
    min_price = int(valid[0])
    max_price = int(valid[-1])
    return f"{min_price}\u2013{max_price} PLN"


def sanitize_services(values: list[str], limit: int = 12) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        if not text or len(text) > 80:
            continue
        normalized = normalize_text(text)
        if not normalized:
            continue
        if normalized in BOOKSY_EXCLUDED_SERVICE_WORDS:
            continue
        if re.fullmatch(r"\d+(?:[,.]\d+)?", normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def https_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def extract_json_candidates(html: str) -> list[Any]:
    candidates: list[Any] = []
    for raw_json in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        decoded = unescape(raw_json).strip()
        if not decoded:
            continue
        try:
            candidates.append(json.loads(decoded))
        except json.JSONDecodeError:
            LOGGER.debug("Could not parse JSON-LD block")
    return candidates


def extract_price_values(value: Any) -> list[Decimal]:
    if value is None:
        return []
    if isinstance(value, (int, float, Decimal)):
        parsed = decimal_from_value(value, default="0")
        return [parsed] if Decimal("1") <= parsed <= Decimal("5000") else []

    text = clean_text(value)
    if not text:
        return []

    prices: list[Decimal] = []
    for raw_price in re.findall(r"(\d{1,4}(?:[,.]\d{1,2})?)\s*(?:zł|zl|PLN)", text, flags=re.IGNORECASE):
        parsed = decimal_from_value(raw_price.replace(",", "."), default="0")
        if Decimal("1") <= parsed <= Decimal("5000"):
            prices.append(parsed)
    return prices


def collect_booksy_data_from_json(value: Any, services: list[str], prices: list[Decimal], parent_key: str = "") -> None:
    if isinstance(value, dict):
        lower_keys = {str(key).lower() for key in value.keys()}
        service_context = "service" in parent_key.lower() or bool(
            lower_keys.intersection({"service", "services", "servicename", "treatment", "treatments"})
        )
        price_context = any("price" in key for key in lower_keys)
        if service_context or price_context:
            for key in ("serviceName", "name", "title"):
                raw_name = value.get(key)
                if isinstance(raw_name, str):
                    services.append(raw_name)
                    break
        for key, nested_value in value.items():
            key_text = str(key)
            if "price" in key_text.lower():
                prices.extend(extract_price_values(nested_value))
            collect_booksy_data_from_json(nested_value, services, prices, key_text)
        return

    if isinstance(value, list):
        for item in value:
            collect_booksy_data_from_json(item, services, prices, parent_key)
        return

    if isinstance(value, str):
        prices.extend(extract_price_values(value))


def normalize_for_district_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(character for character in normalized if not unicodedata.combining(character)).lower()


def district_from_address(address: str) -> str | None:
    normalized_address = normalize_for_district_match(address)
    for district in sorted(WARSAW_DISTRICTS, key=lambda item: len(normalize_for_district_match(item)), reverse=True):
        if normalize_for_district_match(district) in normalized_address:
            return district
    return None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class HttpClient:
    def __init__(self, timeout_seconds: int, retries: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    def get_text(self, url: str, headers: dict[str, str], request_delay: float) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                if request_delay > 0:
                    time.sleep(request_delay)
                request = Request(url, headers=headers)
                with urlopen(request, timeout=self.timeout_seconds, context=https_context()) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return response.read().decode(charset, errors="replace")
            except HTTPError as exc:
                last_error = exc
                if exc.code in {403, 404, 410}:
                    return ""
            except (URLError, TimeoutError) as exc:
                last_error = exc
            if attempt < self.retries:
                time.sleep(min(2**attempt, 10))
        LOGGER.debug("GET text failed for %s: %s", url, last_error)
        return ""

    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str], request_delay: float) -> dict[str, Any]:
        last_error: Exception | None = None
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(1, self.retries + 1):
            try:
                if request_delay > 0:
                    time.sleep(request_delay)
                request = Request(url, data=body, headers=headers, method="POST")
                with urlopen(request, timeout=self.timeout_seconds, context=https_context()) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return json.loads(response.read().decode(charset, errors="replace"))
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(2**attempt, 10))
        LOGGER.debug("POST json failed for %s: %s", url, last_error)
        return {}

    def get_json(self, url: str, headers: dict[str, str], request_delay: float) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                if request_delay > 0:
                    time.sleep(request_delay)
                request = Request(url, headers=headers, method="GET")
                with urlopen(request, timeout=self.timeout_seconds, context=https_context()) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return json.loads(response.read().decode(charset, errors="replace"))
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(2**attempt, 10))
        LOGGER.debug("GET json failed for %s: %s", url, last_error)
        return {}


class BooksyCollector:
    def __init__(self, http: HttpClient, request_delay_seconds: float) -> None:
        self.http = http
        self.request_delay_seconds = request_delay_seconds
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
        }

    def collect(
        self,
        target_per_district: int,
        max_pages: int,
        active_districts: list[str],
        seen_merge_keys: set[str],
        on_page_complete: Callable[[dict[str, list[BooksySalon]]], None],
    ) -> dict[str, list[BooksySalon]]:
        buckets: dict[str, list[BooksySalon]] = {district: [] for district in active_districts}
        seen_urls: set[str] = set()
        category_district_counts: dict[str, dict[str, int]] = {
            category: {district: 0 for district in active_districts} for category in BOOKSY_CATEGORIES
        }

        for category in BOOKSY_CATEGORIES:
            if self._all_districts_full(buckets, target_per_district):
                LOGGER.info("All districts reached target (%s per district)", target_per_district)
                break

            for page in range(1, max_pages + 1):
                if self._all_districts_full(buckets, target_per_district):
                    LOGGER.info("All districts reached target (%s per district)", target_per_district)
                    break

                search_url = BOOKSY_CATEGORY_SEARCH_URL.format(category=category, page=page)
                LOGGER.info("Fetching Booksy category page %s (%s): %s", page, category, search_url)
                search_html = self.http.get_text(search_url, self.headers, self.request_delay_seconds)
                if not search_html:
                    break

                business_urls = self._business_urls_from_search(search_html)
                if not business_urls:
                    break

                for candidate_url in business_urls:
                    if candidate_url in seen_urls:
                        LOGGER.debug("seen url")
                        continue
                    seen_urls.add(candidate_url)

                    business_html = self.http.get_text(candidate_url, self.headers, self.request_delay_seconds)
                    if not business_html:
                        continue

                    salon = self._parse_business_page(business_html, candidate_url)
                    district = district_from_address(salon.address)
                    if district is None:
                        LOGGER.debug("district not found")
                        continue
                    if district not in buckets:
                        LOGGER.debug("district not found")
                        continue
                    if len(buckets[district]) >= target_per_district:
                        LOGGER.debug("district full")
                        continue
                    if not salon.services:
                        LOGGER.debug("no services")
                        continue
                    if category_district_counts[category][district] >= 2:
                        LOGGER.debug("category limit reached for district")
                        continue

                    merge = f"{normalize_text(salon.name)}|{normalize_text(salon.address)}"
                    if merge in seen_merge_keys:
                        continue

                    salon.district = district
                    seen_merge_keys.add(merge)
                    category_district_counts[category][district] += 1
                    buckets[district].append(salon)
                    LOGGER.info(
                        "Collected %s/%s for %s: %s [%s]",
                        len(buckets[district]),
                        target_per_district,
                        district,
                        salon.name,
                        category,
                    )

                on_page_complete(buckets)

            category_total = sum(category_district_counts[category].values())
            LOGGER.info("Finished category %s: %s salons collected total", category, category_total)

        return buckets

    @staticmethod
    def _all_districts_full(buckets: dict[str, list[BooksySalon]], target_per_district: int) -> bool:
        return all(len(salons) >= target_per_district for salons in buckets.values())

    def _business_urls_from_search(self, html: str) -> list[str]:
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
        candidates: list[str] = []
        for href in hrefs:
            absolute = urljoin(BOOKSY_BASE_URL, unescape(href)).split("#", 1)[0]
            if "booksy.com/pl-pl/" not in absolute:
                continue
            if "/s?" in absolute or "/s/" in absolute:
                continue
            if not re.search(r"/pl-pl/\d+_[^/?]+", absolute):
                continue
            candidates.append(absolute)
        deduped: list[str] = []
        seen: set[str] = set()
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped

    def _parse_business_page(self, html: str, url: str) -> BooksySalon:
        services: list[str] = []
        price_values: list[Decimal] = []
        name = ""
        address = ""
        phone = "Not available"
        rating = 0.0
        review_count = 0

        for candidate in extract_json_candidates(html):
            self._extract_meta_from_json(candidate, services, price_values)
            if isinstance(candidate, dict):
                if not name:
                    name = clean_text(candidate.get("name"))
                if not address:
                    address = self._extract_address(candidate)
                if rating <= 0:
                    aggregate = candidate.get("aggregateRating")
                    if isinstance(aggregate, dict):
                        rating = safe_float(aggregate.get("ratingValue"), default=rating)
                        review_count = max(review_count, safe_int(aggregate.get("reviewCount"), default=review_count))

        services.extend(self._extract_service_names_from_html(html))
        price_values.extend(extract_price_values(html))

        if not name:
            name = self._extract_name_from_html(html)
        if not address:
            address = self._extract_address_from_html(html)
        if rating <= 0:
            rating = self._extract_rating_from_html(html)
        if review_count <= 0:
            review_count = self._extract_review_count_from_html(html)

        cleaned_services = sanitize_services(services)
        normalized_business_name = normalize_text(name or "")
        if normalized_business_name:
            cleaned_services = [
                service for service in cleaned_services if normalize_text(service) != normalized_business_name
            ]

        final_address = address or "Not available"
        final_phone = "Not available"
        final_price = format_price_range(price_values) or "Not available"

        return BooksySalon(
            name=name or "Not available",
            address=final_address,
            district="",
            phone=final_phone,
            website_url=url,
            services=cleaned_services,
            price_range=final_price,
            rating=round(rating, 2) if rating > 0 else 0.0,
            review_count=review_count,
        )

    def _extract_meta_from_json(self, value: Any, services: list[str], prices: list[Decimal]) -> None:
        collect_booksy_data_from_json(value, services, prices)

    def _extract_address(self, data: dict[str, Any]) -> str:
        address = data.get("address")
        if isinstance(address, str):
            return clean_text(address)
        if isinstance(address, dict):
            parts = [
                clean_text(address.get("streetAddress")),
                clean_text(address.get("addressLocality")),
                clean_text(address.get("postalCode")),
                clean_text(address.get("addressCountry")),
            ]
            return clean_text(", ".join([part for part in parts if part]))
        return ""

    def _extract_service_names_from_html(self, html: str) -> list[str]:
        decoded = unescape(html)
        services: list[str] = []
        for pattern in [
            r'"serviceName"\s*:\s*"([^"]{3,120})"',
            r'"service_name"\s*:\s*"([^"]{3,120})"',
            r'data-testid=["\']service-name["\'][^>]*>([^<]{3,120})<',
            r'"name"\s*:\s*"([^"]{3,120})"\s*,\s*"price"',
        ]:
            services.extend(re.findall(pattern, decoded, flags=re.IGNORECASE))
        return services

    def _extract_name_from_html(self, html: str) -> str:
        for pattern in [
            r"<title>\s*([^<]+?)\s*(?:\||-)\s*Booksy",
            r"<h1[^>]*>([^<]{2,200})</h1>",
            r'"name"\s*:\s*"([^"]{2,200})"',
        ]:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                return clean_text(match.group(1))
        return ""

    def _extract_address_from_html(self, html: str) -> str:
        for pattern in [
            r'"address"\s*:\s*"([^"]{5,300})"',
            r'data-testid=["\']business-address["\'][^>]*>([^<]{5,300})<',
        ]:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                return clean_text(match.group(1))
        return ""

    def _extract_rating_from_html(self, html: str) -> float:
        for pattern in [
            r'"ratingValue"\s*:\s*"?([0-5](?:[.,]\d)?)"?',
            r'data-testid=["\']rating-value["\'][^>]*>([0-5](?:[.,]\d)?)<',
        ]:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                return safe_float(match.group(1).replace(",", "."))
        return 0.0

    def _extract_review_count_from_html(self, html: str) -> int:
        for pattern in [
            r'"reviewCount"\s*:\s*"?(\d+)"?',
            r'data-testid=["\']reviews-count["\'][^>]*>\s*\(?(\d+)\)?',
        ]:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                return safe_int(match.group(1))
        return 0


class GooglePlacesPhoneEnricher:
    def __init__(self, api_key: str, http: HttpClient, request_delay_seconds: float, workers: int) -> None:
        self.api_key = api_key
        self.http = http
        self.request_delay_seconds = request_delay_seconds
        self.workers = max(1, workers)
        self._thread_delay_lock = threading.Lock()
        self._last_request_at: dict[int, float] = {}

    def enrich_phones(self, salons: list[BooksySalon]) -> dict[int, tuple[str, str]]:
        if not salons:
            return {}
        LOGGER.info("Google phone enrichment for %s salon(s)", len(salons))
        results: dict[int, tuple[str, str]] = {}
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_map = {executor.submit(self._fetch_phone, salons[index]): index for index in range(len(salons))}
            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    phone, place_id = future.result()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("Google fallback failed for %s: %s", salons[index].name, exc)
                    phone, place_id = "Not available", ""
                results[index] = (phone, place_id)
        return results

    def _fetch_phone(self, salon: BooksySalon) -> tuple[str, str]:
        query = f"{salon.name} Warszawa"
        search_payload = {"textQuery": query, "languageCode": "pl", "regionCode": "PL", "maxResultCount": 3}
        search_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName",
        }
        self._thread_delay()
        search_result = self.http.post_json(GOOGLE_SEARCH_URL, search_payload, search_headers, request_delay=0.0)
        places = search_result.get("places") if isinstance(search_result, dict) else None
        if not isinstance(places, list) or not places:
            return "Not available", ""

        place_id = clean_text((places[0] or {}).get("id"))
        if not place_id:
            return "Not available", ""

        details_url = f"https://places.googleapis.com/v1/places/{place_id}"
        details_headers = {
            "Accept": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "id,nationalPhoneNumber",
        }
        self._thread_delay()
        details = self.http.get_json(details_url, details_headers, request_delay=0.0)
        phone = clean_text(details.get("nationalPhoneNumber")) if isinstance(details, dict) else ""
        return (phone or "Not available"), place_id

    def _thread_delay(self) -> None:
        if self.request_delay_seconds <= 0:
            return
        thread_id = threading.get_ident()
        with self._thread_delay_lock:
            now = time.monotonic()
            last = self._last_request_at.get(thread_id, 0.0)
            wait_for = self.request_delay_seconds - (now - last)
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_request_at[thread_id] = time.monotonic()


def to_output_record(salon: BooksySalon, external_id: str = "") -> dict[str, Any]:
    return {
        "name": salon.name,
        "address": salon.address or "Not available",
        "district": salon.district,
        "phone": salon.phone or "Not available",
        "websiteUrl": salon.website_url,
        "services": salon.services,
        "priceRange": salon.price_range or "Not available",
        "rating": round(float(salon.rating), 2),
        "reviewCount": int(salon.review_count),
        "source": "Booksy + Google Places API",
        "externalId": external_id or "",
    }


def merge_key(record: dict[str, Any]) -> str:
    return f"{normalize_text(record['name'])}|{normalize_text(record['address'])}"


def write_checkpoint(records: list[dict[str, Any]], output_paths: list[Path]) -> None:
    payload = json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    for output_path in output_paths:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        LOGGER.info("Checkpoint saved: %s record(s) to %s", len(records), output_path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Warsaw salon data (Booksy-first).")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output JSON path.")
    parser.add_argument("--target-per-district", type=int, default=7, help="Salons per district.")
    parser.add_argument("--candidate-limit", type=int, default=10, help="Max Booksy candidates per district.")
    parser.add_argument("--max-pages", type=int, default=10, help="Maximum Booksy search pages to paginate.")
    parser.add_argument("--booksy-delay", type=float, default=0.8, help="Delay between Booksy requests in seconds.")
    parser.add_argument("--google-delay", type=float, default=0.15, help="Delay between Google requests per thread.")
    parser.add_argument("--google-workers", type=int, default=4, help="Google enrichment thread pool size.")
    parser.add_argument(
        "--district",
        action="append",
        choices=WARSAW_DISTRICTS,
        help="Collect only this district (can be repeated).",
    )
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retry count.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args(argv)


def salons_to_records(salons: list[BooksySalon]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for salon in salons:
        record = to_output_record(salon, external_id=salon.external_id)
        key = merge_key(record)
        if key in seen:
            continue
        seen.add(key)
        records.append(record)
    return records


def flatten_buckets(buckets: dict[str, list[BooksySalon]]) -> list[BooksySalon]:
    salons: list[BooksySalon] = []
    for district in WARSAW_DISTRICTS:
        if district in buckets:
            salons.extend(buckets[district])
    return salons


def collect_all(args: argparse.Namespace) -> tuple[list[dict[str, Any]], bool]:
    load_dotenv(
        [
            SCRIPT_DIR / ".env",
            BACKEND_OUTPUT_PATH.parent / ".env",
            PROJECT_ROOT / ".env",
            Path.cwd() / ".env",
        ]
    )
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    output_paths = [LOCAL_OUTPUT_PATH, BACKEND_OUTPUT_PATH]
    if args.output.resolve() not in {path.resolve() for path in output_paths}:
        output_paths.append(args.output)

    active_districts = args.district or WARSAW_DISTRICTS
    http = HttpClient(timeout_seconds=args.timeout, retries=args.retries)
    booksy = BooksyCollector(http=http, request_delay_seconds=args.booksy_delay)
    google = None
    if api_key:
        google = GooglePlacesPhoneEnricher(
            api_key=api_key,
            http=http,
            request_delay_seconds=args.google_delay,
            workers=args.google_workers,
        )
    else:
        LOGGER.warning("GOOGLE_PLACES_API_KEY is missing, phone fallback will be skipped.")

    records: list[dict[str, Any]] = []
    seen_merge_keys: set[str] = set()
    buckets: dict[str, list[BooksySalon]] = {}

    def checkpoint_from_buckets(bucket_state: dict[str, list[BooksySalon]]) -> None:
        nonlocal records
        all_salons = flatten_buckets(bucket_state)
        if google is not None:
            phone_updates = google.enrich_phones(all_salons)
            for index, (phone, place_id) in phone_updates.items():
                if phone and phone != "Not available":
                    all_salons[index].phone = phone
                if place_id:
                    all_salons[index].external_id = place_id
        records = salons_to_records(all_salons)
        write_checkpoint(records, output_paths)

    try:
        buckets = booksy.collect(
            target_per_district=args.target_per_district,
            max_pages=args.max_pages,
            active_districts=active_districts,
            seen_merge_keys=seen_merge_keys,
            on_page_complete=checkpoint_from_buckets,
        )
    except KeyboardInterrupt:
        if buckets:
            checkpoint_from_buckets(buckets)
        else:
            write_checkpoint(records, output_paths)
        return records, True

    return records, False


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")

    records, interrupted = collect_all(args)
    if interrupted:
        LOGGER.warning("Interrupted by user, partial results saved.")
        return 130

    LOGGER.info("Done. Collected %s records.", len(records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

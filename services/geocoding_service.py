from decimal import Decimal, InvalidOperation
import re
import requests
import os
import logging

GEOAPIFY_SEARCH_URL = "https://api.geoapify.com/v1/geocode/search"
DEFAULT_STATE = "Maharashtra"
DEFAULT_COUNTRY = "India"

# Configure logging
logger = logging.getLogger("geocoding_service")


def validate_address(address):
    return bool(address and address.strip())


def normalize_text(value):
    if not value:
        return ""

    return re.sub(r"\s+", " ", value.strip()).lower()


def contains_text(full_text, substring):
    return bool(substring and normalize_text(substring) in normalize_text(full_text))


def join_address_parts(parts):
    cleaned_parts = []

    for part in parts:
        if not part or not part.strip():
            continue

        normalized = normalize_text(part)
        if normalized in (normalize_text(p) for p in cleaned_parts):
            continue

        cleaned_parts.append(part.strip())

    return ", ".join(cleaned_parts)


def build_station_search_address(station_name, city, address):
    """
    Build a complete searchable address for OpenStreetMap.
    """

    parts = [station_name, address]

    if city and not contains_text(address, city):
        parts.append(city)

    if DEFAULT_STATE and not contains_text(address, DEFAULT_STATE):
        parts.append(DEFAULT_STATE)

    if DEFAULT_COUNTRY and not contains_text(address, DEFAULT_COUNTRY):
        parts.append(DEFAULT_COUNTRY)

    return join_address_parts(parts)


def build_address_fallback(city, address):
    parts = [address]

    if city and not contains_text(address, city):
        parts.append(city)

    if DEFAULT_STATE and not contains_text(address, DEFAULT_STATE):
        parts.append(DEFAULT_STATE)

    if DEFAULT_COUNTRY and not contains_text(address, DEFAULT_COUNTRY):
        parts.append(DEFAULT_COUNTRY)

    return join_address_parts(parts)


def build_city_fallback(city):
    return join_address_parts([city, DEFAULT_STATE, DEFAULT_COUNTRY])


def build_plus_code_fallback(address, city):
    plus_code_search = None
    if address:
        match = re.search(r"[A-Z0-9]{4}\+[A-Z0-9]{2,4}", address.upper())
        if match:
            plus_code_search = match.group(0)

    if not plus_code_search:
        return None

    parts = [plus_code_search]

    if city and not contains_text(plus_code_search, city):
        parts.append(city)

    if DEFAULT_STATE and not contains_text(plus_code_search, DEFAULT_STATE):
        parts.append(DEFAULT_STATE)

    if DEFAULT_COUNTRY and not contains_text(plus_code_search, DEFAULT_COUNTRY):
        parts.append(DEFAULT_COUNTRY)

    return join_address_parts(parts)


def get_station_coordinates(station_name, city, address):
    search_attempts = []

    # Use the most specific search forms first (address without station name is cleaner for geocoders).
    if address:
        search_attempts.append(build_address_fallback(city, address))
        plus_code_search = build_plus_code_fallback(address, city)
        if plus_code_search:
            search_attempts.append(plus_code_search)

        # Heuristic: Try to search using only the last parts of the address (neighborhood, sub-locality, city)
        address_parts = [p.strip() for p in address.split(',')]
        if len(address_parts) >= 2:
            for i in range(2, min(len(address_parts) + 1, 4)):
                partial_address = ", ".join(address_parts[-i:])
                search_attempts.append(build_address_fallback(city, partial_address))

    if station_name or address:
        search_attempts.append(build_station_search_address(station_name, city, address))

    if city:
        # Final fallback to city center coordinates so adding the station is never blocked
        search_attempts.append(build_city_fallback(city))

    for search_address in search_attempts:
        coordinates = get_coordinates(search_address)

        if coordinates is not None:
            coordinates["search_address"] = search_address
            return coordinates

    return None


def parse_coordinate(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def get_coordinates(full_address):
    """
    Geocodes full_address using Geoapify Forward Geocoding API.
    Returns:
    {
        "latitude": Decimal,
        "longitude": Decimal,
        "display_name": str
    }
    OR
    None
    """
    if not validate_address(full_address):
        logger.warning("Empty or invalid address provided for geocoding.")
        return None

    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        logger.error("GEOAPIFY_API_KEY environment variable is not configured or is empty.")
        return None

    try:
        response = requests.get(
            GEOAPIFY_SEARCH_URL,
            params={
                "text": full_address,
                "format": "json",
                "apiKey": api_key,
                "limit": 1,
                "filter": "countrycode:in",
            },
            timeout=15
        )

        if response.status_code == 401:
            logger.error("Invalid Geoapify API key provided.")
            return None
        elif response.status_code == 429:
            logger.error("Geoapify API rate limit exceeded.")
            return None

        response.raise_for_status()
        data = response.json()
        results = data.get("results")

    except requests.RequestException as error:
        logger.exception(f"Network or request failure when geocoding: {error}")
        return None
    except ValueError as error:
        logger.exception(f"Failed to parse JSON response from Geoapify: {error}")
        return None

    if not results:
        logger.info(f"No geocoding results found for address: '{full_address}'")
        return None

    best = results[0]
    lat_val = best.get("lat")
    lon_val = best.get("lon")

    lat = parse_coordinate(lat_val)
    lon = parse_coordinate(lon_val)

    if lat is None or lon is None:
        logger.error(f"Failed to parse coordinates: lat={lat_val}, lon={lon_val}")
        return None

    display_name = best.get("formatted", "")

    logger.info(f"Successfully geocoded address to: lat={lat}, lon={lon}, display_name='{display_name}'")
    return {
        "latitude": lat,
        "longitude": lon,
        "display_name": display_name,
    }

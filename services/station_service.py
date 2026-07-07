import math
import logging
from sqlalchemy.exc import SQLAlchemyError

from database.db import db
from models.charger import ChargerStatus
from services.charger_service import charger_to_public_dict
from models.station import Station

logger = logging.getLogger(__name__)


def get_all_stations():
    """Return all stations ordered for public discovery pages."""
    try:
        return Station.query.order_by(Station.city, Station.station_name).all()
    except SQLAlchemyError:
        db.session.rollback()
        return []


def search_station(search_query="", status_filter="All"):
    """Search and filter stations for the admin station list."""
    try:
        query = Station.query
        search_query = (search_query or "").strip()
        status_filter = status_filter or "All"

        has_search_filter = bool(search_query)
        has_status_filter = status_filter in {"Active", "Inactive"}

        if has_search_filter:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                db.or_(
                    Station.station_name.ilike(search_pattern),
                    Station.city.ilike(search_pattern),
                )
            )

        if has_status_filter:
            query = query.filter(Station.status == status_filter)

        if not has_search_filter and not has_status_filter:
            return get_all_stations()

        return query.order_by(Station.station_id.desc()).all()
    except SQLAlchemyError:
        db.session.rollback()
        return []


def get_station_by_id(station_id):
    """Return one station by primary key, or None when unavailable."""
    try:
        return db.session.get(Station, station_id)
    except (TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        return None


def create_station(data):
    """Create a station record."""
    try:
        station = Station(**data)
        db.session.add(station)
        db.session.commit()
        return station
    except SQLAlchemyError:
        db.session.rollback()
        return None


def update_station(station_id, data):
    """Update station columns from a dictionary."""
    station = get_station_by_id(station_id)

    if station is None:
        return None

    try:
        for key, value in data.items():
            if hasattr(station, key):
                setattr(station, key, value)

        db.session.commit()
        return station
    except SQLAlchemyError:
        db.session.rollback()
        return None


def delete_station(station_id):
    """Delete a station only when no chargers are linked to it."""
    station = get_station_by_id(station_id)

    if station is None:
        return False, "Station not found."

    if station.chargers:
        return False, "Station cannot be deleted because chargers exist."

    try:
        db.session.delete(station)
        db.session.commit()
        return True, "Station deleted successfully."
    except SQLAlchemyError:
        db.session.rollback()
        return False, "Station could not be deleted."


def station_address_exists(address, current_station_id=None):
    """Check duplicate complete station addresses, excluding the current row."""
    try:
        normalized_address = normalize_address(address)
        query = Station.query.filter(
            normalized_station_address() == normalized_address
        )

        if current_station_id:
            query = query.filter(Station.station_id != current_station_id)

        return query.first() is not None
    except SQLAlchemyError:
        db.session.rollback()
        return True


def station_coordinates_exist(latitude, longitude, current_station_id=None):
    """Check duplicate station coordinates, excluding the current row."""
    try:
        query = Station.query.filter(
            Station.latitude == latitude,
            Station.longitude == longitude,
        )

        if current_station_id:
            query = query.filter(Station.station_id != current_station_id)

        return query.first() is not None
    except SQLAlchemyError:
        db.session.rollback()
        return True


def normalize_address(address):
    return " ".join((address or "").strip().lower().split())


def normalized_station_address():
    return db.func.lower(
        db.func.regexp_replace(
            db.func.trim(Station.address),
            "[[:space:]]+",
            " ",
            "g",
        )
    )


def station_to_admin_dict(station):
    """Convert a station model for admin list rendering."""
    data = station_to_discovery_dict(station)
    data["image_url"] = station.image_url
    return data


def station_to_discovery_dict(station):
    """Convert a station model into the shape used by the discovery UI."""
    chargers = list(station.chargers)
    available_count = sum(
        1 for charger in chargers if charger.status == ChargerStatus.AVAILABLE
    )
    busy_count = sum(
        1 for charger in chargers if charger.status == ChargerStatus.BUSY
    )
    offline_count = sum(
        1 for charger in chargers if charger.status == ChargerStatus.OFFLINE
    )
    maintenance_count = sum(
        1 for charger in chargers if charger.status == ChargerStatus.MAINTENANCE
    )

    connector_types = sorted(
        {charger.connector_type for charger in chargers if charger.connector_type}
    )
    opening_time = station.opening_time.isoformat() if station.opening_time else None
    closing_time = station.closing_time.isoformat() if station.closing_time else None

    return {
        "id": station.station_id,
        "station_id": station.station_id,
        "station_name": station.station_name,
        "city": station.city,
        "address": station.address,
        "latitude": float(station.latitude) if station.latitude is not None else None,
        "longitude": (
            float(station.longitude) if station.longitude is not None else None
        ),
        "display_name": station.display_name,
        "description": station.description,
        "image_url": station.image_url,
        "price_per_kwh": (
            float(station.price_per_kwh)
            if station.price_per_kwh is not None
            else None
        ),
        "is_open_24_hours": station.is_open_24_hours,
        "opening_time": opening_time,
        "closing_time": closing_time,
        "operating_hours": build_operating_hours_label(
            station.is_open_24_hours,
            opening_time,
            closing_time,
        ),
        "status": station.status,
        "connector_types": connector_types,
        "vehicle_types": sorted(
            {charger.vehicle_type for charger in chargers if charger.vehicle_type}
        ),
        "chargers": [charger_to_public_dict(charger) for charger in chargers],
        "total_chargers": len(chargers),
        "available_chargers": available_count,
        "busy_chargers": busy_count,
        "offline_chargers": offline_count + maintenance_count,
        "maintenance_chargers": maintenance_count,
    }


def build_operating_hours_label(is_open_24_hours, opening_time, closing_time):
    if is_open_24_hours:
        return "Open 24 Hours"

    return f"{format_time_label(opening_time)} - {format_time_label(closing_time)}"


def format_time_label(value):
    if not value:
        return "Not set"

    return value[:5]


def calculate_distance_meters(lat1, lon1, lat2, lon2):
    """Compute direct distance in meters using Haversine formula."""
    degrees_to_radians = math.pi / 180.0
    phi1 = float(lat1) * degrees_to_radians
    phi2 = float(lat2) * degrees_to_radians
    lambda1 = float(lon1) * degrees_to_radians
    lambda2 = float(lon2) * degrees_to_radians

    dphi = phi2 - phi1
    dlambda = lambda2 - lambda1

    a = (math.sin(dphi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    
    return 2.0 * 6371000.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def is_station_exact_duplicate(station_name, address, latitude, longitude, current_station_id=None):
    """Flag as duplicate if any existing station has the exact same name, address, latitude, and longitude."""
    try:
        lat_val = float(latitude)
        lon_val = float(longitude)
    except (ValueError, TypeError):
        logger.warning(f"Invalid coordinate arguments passed to exact check. Lat: {latitude}, Lon: {longitude}")
        return False

    name_norm = " ".join((station_name or "").strip().lower().split())
    addr_norm = " ".join((address or "").strip().lower().split())

    duplicate_found = False
    all_stations = Station.query.all()

    for station in all_stations:
        if current_station_id and station.station_id == current_station_id:
            continue
        try:
            s_name_norm = " ".join((station.station_name or "").strip().lower().split())
            s_addr_norm = " ".join((station.address or "").strip().lower().split())

            if (s_name_norm == name_norm and
                s_addr_norm == addr_norm and
                abs(float(station.latitude) - lat_val) < 1e-6 and
                abs(float(station.longitude) - lon_val) < 1e-6):
                
                duplicate_found = True
                logger.info(f"Exact Duplicate: Match found for station '{station.station_name}' (ID: {station.station_id})")
                break
        except (ValueError, TypeError):
            continue

    logger.info(
        f"Exact Duplicate Check Result:\n"
        f"  Station Name: {station_name}\n"
        f"  Address: {address}\n"
        f"  Latitude: {lat_val}\n"
        f"  Longitude: {lon_val}\n"
        f"  Is Duplicate: {duplicate_found}"
    )

    return duplicate_found


def get_stations_near_coords(lat, lon, radius_km=10.0):
    """Return active stations within radius_km of coordinates, sorted by distance."""
    try:
        active_stations = Station.query.filter(
            Station.status == "Active",
            Station.latitude.isnot(None),
            Station.longitude.isnot(None)
        ).all()

        nearby = []
        for station in active_stations:
            dist_m = calculate_distance_meters(lat, lon, station.latitude, station.longitude)
            dist_km = dist_m / 1000.0
            if dist_km <= radius_km:
                nearby.append((station, dist_km))

        # Sort by distance
        nearby.sort(key=lambda x: x[1])

        results = []
        for station, dist_km in nearby:
            dict_data = station_to_discovery_dict(station)
            dict_data["distance_km"] = dist_km
            results.append(dict_data)

        return results
    except SQLAlchemyError:
        db.session.rollback()
        return []


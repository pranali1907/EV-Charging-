from flask import Blueprint, render_template, request, jsonify
import requests


from services.station_service import (
    get_all_stations,
    get_station_by_id,
    station_to_discovery_dict,
    get_stations_near_coords,
    calculate_distance_meters,
)
from services.geocoding_service import get_coordinates

home_bp = Blueprint("home", __name__)


@home_bp.before_request
def auto_update_statuses():
    from services.charger_service import update_charger_statuses
    update_charger_statuses()


def parse_natural_query(query_str):
    if not query_str:
        return "", "text"
    
    ignore_words = {
        "charging", "station", "stations", "charger", "ev",
        "electric", "find", "search", "around", "near", "nearby", "in", "at"
    }
    
    words = query_str.lower().split()
    
    geo_keywords = {"near me", "nearby", "near by", "near by me", "charging station near me", "ev near me"}
    if query_str.lower().strip() in geo_keywords:
        return "", "near_me"
        
    brand_keywords = {
        "tata", "chargezone", "statiq", "ather", "jio", "malu", "zeon", "adani", "bpcl", "goego", "e-fill", "efill",
        "ccs2", "type-2", "leccs", "15a", "socket", "connector"
    }
    if any(bk in words for bk in brand_keywords):
        return "", "text"
        
    search_mode = "near"
    if "in" in words:
        search_mode = "in"
    elif "near" in words:
        search_mode = "near"
        
    location_words = [w for w in words if w not in ignore_words]
    location_name = " ".join(location_words).strip()
    
    return location_name, search_mode


@home_bp.route("/api/search")
def search_api():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    radius = request.args.get("radius", "10")

    if lat and lon:
        try:
            lat_val = float(lat)
            lon_val = float(lon)
            radius_val = float(radius)
            results = get_stations_near_coords(lat_val, lon_val, radius_val)
            for station in results:
                operator = "Unknown"
                name_lower = station["station_name"].lower()
                if "tata power" in name_lower:
                    operator = "Tata Power"
                elif "chargezone" in name_lower or "charge zone" in name_lower:
                    operator = "ChargeZone"
                elif "statiq" in name_lower:
                    operator = "Statiq"
                elif "ather grid" in name_lower or "ather" in name_lower:
                    operator = "Ather Grid"
                elif "jio-bp" in name_lower or "jio" in name_lower:
                    operator = "Jio-bp Pulse"
                station["operator"] = operator
            return jsonify(results)
        except ValueError:
            return jsonify({"error": "Invalid coordinates or radius"}), 400

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    location_name, search_mode = parse_natural_query(query)

    if location_name:
        # First check for exact city match case-insensitively to avoid geocoding issues for standard cities
        stations = get_all_stations()
        city_matches = []
        for station in stations:
            if station.status != "Active":
                continue
            station_city_lower = (station.city or "").strip().lower()
            query_lower = location_name.lower()
            # Support partial inclusion checks for full display names/queries
            if station_city_lower and (station_city_lower in query_lower or query_lower in station_city_lower):
                dict_data = station_to_discovery_dict(station)
                dict_data["distance_km"] = 0.0
                
                # Attach operator
                operator = "Unknown"
                name_lower = dict_data["station_name"].lower()
                if "tata power" in name_lower:
                    operator = "Tata Power"
                elif "chargezone" in name_lower or "charge zone" in name_lower:
                    operator = "ChargeZone"
                elif "statiq" in name_lower:
                    operator = "Statiq"
                elif "ather grid" in name_lower or "ather" in name_lower:
                    operator = "Ather Grid"
                elif "jio-bp" in name_lower or "jio" in name_lower:
                    operator = "Jio-bp Pulse"
                dict_data["operator"] = operator
                city_matches.append(dict_data)

        if city_matches:
            return jsonify(city_matches)

        coords = get_coordinates(location_name)
        if coords:
            lat_val = float(coords["latitude"])
            lon_val = float(coords["longitude"])
            radius_val = float(request.args.get("radius", 10.0))

            stations = get_all_stations()
            results = []

            for station in stations:
                if station.status != "Active" or station.latitude is None or station.longitude is None:
                    continue

                dist_m = calculate_distance_meters(lat_val, lon_val, station.latitude, station.longitude)
                dist_km = dist_m / 1000.0

                if search_mode == "in":
                    # Check exact city match (case-insensitive)
                    city_match = False
                    if station.city:
                        sc_lower = station.city.lower()
                        loc_lower = location_name.lower()
                        if loc_lower in sc_lower or sc_lower in loc_lower:
                            city_match = True
                    if not city_match:
                        continue
                else: # Mode 2: "near"
                    if dist_km > radius_val:
                        continue

                dict_data = station_to_discovery_dict(station)
                dict_data["distance_km"] = dist_km

                # Attach operator
                operator = "Unknown"
                name_lower = dict_data["station_name"].lower()
                if "tata power" in name_lower:
                    operator = "Tata Power"
                elif "chargezone" in name_lower or "charge zone" in name_lower:
                    operator = "ChargeZone"
                elif "statiq" in name_lower:
                    operator = "Statiq"
                elif "ather grid" in name_lower or "ather" in name_lower:
                    operator = "Ather Grid"
                elif "jio-bp" in name_lower or "jio" in name_lower:
                    operator = "Jio-bp Pulse"
                dict_data["operator"] = operator

                results.append(dict_data)

            results.sort(key=lambda x: x["distance_km"])
            return jsonify(results)

    # Fallback to standard text search if no location geocoded or brand keyword search
    stations = get_all_stations()
    station_data = [station_to_discovery_dict(station) for station in stations]
    results = []

    query_lower = query.lower()
    for station in station_data:
        operator = "Unknown"
        name_lower = station["station_name"].lower()
        if "tata power" in name_lower:
            operator = "Tata Power"
        elif "chargezone" in name_lower or "charge zone" in name_lower:
            operator = "ChargeZone"
        elif "statiq" in name_lower:
            operator = "Statiq"
        elif "ather grid" in name_lower or "ather" in name_lower:
            operator = "Ather Grid"
        elif "jio-bp" in name_lower or "jio" in name_lower:
            operator = "Jio-bp Pulse"

        station["operator"] = operator

        search_blob = " ".join([
            station["station_name"],
            station["city"],
            station["address"],
            station.get("display_name") or "",
            station.get("description") or "",
            operator,
            " ".join(station["connector_types"])
        ]).lower()

        keywords = query_lower.split()
        is_match = True
        for kw in keywords:
            if kw not in search_blob:
                kw_match = False
                for word in search_blob.split():
                    if len(kw) >= 4 and len(word) >= 4:
                        if edit_distance_1(kw, word):
                            kw_match = True
                            break
                if not kw_match:
                    is_match = False
                    break

        if is_match:
            results.append(station)

    return jsonify(results[:15])


def edit_distance_1(w1, w2):
    if abs(len(w1) - len(w2)) > 1:
        return False
    if len(w1) == len(w2):
        diffs = sum(1 for c1, c2 in zip(w1, w2) if c1 != c2)
        return diffs <= 1
    longer, shorter = (w1, w2) if len(w1) > len(w2) else (w2, w1)
    i = j = diffs = 0
    while i < len(longer) and j < len(shorter):
        if longer[i] != shorter[j]:
            diffs += 1
            if diffs > 1:
                return False
            i += 1
        else:
            i += 1
            j += 1
    return True


@home_bp.route("/")
def index():
    stations = get_all_stations()
    station_data = [station_to_discovery_dict(station) for station in stations]
    connector_filters = sorted(
        {
            connector
            for station in station_data
            for connector in station["connector_types"]
        }
    )

    return render_template(
        "index.html",
        connector_filters=connector_filters,
        stations=station_data,
    )


@home_bp.route("/station/<int:station_id>")
def station_details(station_id):
    station = get_station_by_id(station_id)

    if station is None:
        return (
            render_template(
                "404.html",
                message="The requested charging station was not found.",
            ),
            404,
        )

    from datetime import datetime
    from models.booking import Booking, BookingStatus
    
    # Enrich each charger with current booking details and next available time
    now_dt = datetime.now()
    now_time = now_dt.time()
    
    enriched_chargers = []
    for chg in station.chargers:
        # Check current active booking
        active_b = Booking.query.filter(
            Booking.charger_id == chg.charger_id,
            Booking.booking_date == now_dt.date(),
            Booking.booking_start_time <= now_time,
            Booking.booking_end_time > now_time,
            Booking.booking_status.in_([BookingStatus.CONFIRMED, BookingStatus.CHARGING])
        ).first()
        
        current_booking_str = "None"
        next_available_time = "Now"
        
        if active_b:
            start_str = active_b.booking_start_time.strftime("%I:%M %p")
            end_str = active_b.booking_end_time.strftime("%I:%M %p")
            current_booking_str = f"Active: {start_str} - {end_str}"
            next_available_time = end_str
        elif chg.status.value in ["Offline", "Maintenance"]:
            next_available_time = "N/A (Offline)"
            
        chg_dict = {
            "charger_id": chg.charger_id,
            "charger_name": chg.charger_name,
            "connector_type": chg.connector_type,
            "power_kw": float(chg.power_kw or 0.0),
            "vehicle_type": chg.vehicle_type,
            "status": chg.status.value,
            "current_booking": current_booking_str,
            "next_available_time": next_available_time
        }
        enriched_chargers.append(chg_dict)

    station_data = station_to_discovery_dict(station)
    charger_overview = build_charger_overview(station_data)
    charging_info = build_charging_info(station_data)
    amenities = [
        {"label": "Parking", "icon": "fa-square-parking"},
        {"label": "Washroom", "icon": "fa-restroom"},
        {"label": "Cafe", "icon": "fa-mug-saucer"},
        {"label": "24x7", "icon": "fa-clock"},
        {"label": "Security", "icon": "fa-shield-halved"},
        {"label": "CCTV", "icon": "fa-video"},
    ]

    return render_template(
        "station_details.html",
        station=station_data,
        enriched_chargers=enriched_chargers,
        charger_overview=charger_overview,
        charging_info=charging_info,
    )


def build_charger_overview(station):
    total = station["total_chargers"]
    available = station["available_chargers"]
    busy = station.get("busy_chargers", 0)
    offline = station.get("offline_chargers", 0)

    return [
        {"label": "Total Chargers", "value": total, "icon": "fa-charging-station"},
        {"label": "Available", "value": available, "icon": "fa-circle-check"},
        {"label": "Busy", "value": busy, "icon": "fa-hourglass-half"},
        {"label": "Offline", "value": offline, "icon": "fa-plug-circle-xmark"},
    ]


def build_charging_info(station):
    has_fast_connector = any(
        connector in station["connector_types"] for connector in ["CCS2", "LECCS"]
    )
    charging_speed = (
        "Fast and standard charging"
        if has_fast_connector
        else "Standard AC charging"
    )

    return [
        {"label": "Charging Speed", "value": charging_speed},
        {"label": "Operating Hours", "value": station["operating_hours"]},
        {"label": "Payment Methods", "value": "UPI, Card, Net Banking"},
        {"label": "Supported Vehicles", "value": "Two-wheelers, cars, and fleet EVs"},
    ]


@home_bp.route("/api/geocode/search")
def geocode_search_api():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    headers = {"User-Agent": "ChargeLive/1.0 (College Project)"}

    def _normalize_name(value):
        text = (value or "").strip().lower()
        return " ".join(text.split()) if text else None

    def _coords_key(lat, lon):
        try:
            return f"{float(lat):.6f},{float(lon):.6f}"
        except (TypeError, ValueError):
            return None

    def _dedupe_locations(items):
        seen_names = set()
        seen_coords = set()
        deduped = []

        for item in items:
            name_key = _normalize_name(item.get("display_name") or item.get("name"))
            coords_key = _coords_key(item.get("latitude"), item.get("longitude"))

            if name_key and name_key in seen_names:
                continue
            if coords_key and coords_key in seen_coords:
                continue

            if name_key:
                seen_names.add(name_key)
            if coords_key:
                seen_coords.add(coords_key)

            deduped.append(item)

        return deduped

    # 1. Try Photon API first
    try:
        response = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": query, "limit": 10},
            headers=headers,
            timeout=8,
        )
        if response.status_code == 200:
            data = response.json()
            features = data.get("features", [])
            results = []
            for feature in features:
                try:
                    coords = feature.get("geometry", {}).get("coordinates", [])
                    if len(coords) < 2:
                        continue

                    props = feature.get("properties", {})
                    name = props.get("name", "")
                    city = props.get("city", "")
                    state = props.get("state", "")
                    country = props.get("country", "")

                    components = []
                    if name:
                        components.append(name)
                    if city and city != name:
                        components.append(city)
                    if state:
                        components.append(state)
                    if country:
                        components.append(country)

                    display_name = ", ".join(components)

                    results.append({
                        "display_name": display_name,
                        "name": name,
                        "city": city,
                        "state": state,
                        "country": country,
                        "latitude": float(coords[1]),
                        "longitude": float(coords[0]),
                    })
                except (TypeError, ValueError, KeyError):
                    continue
            if results:
                return jsonify(_dedupe_locations(results))
    except Exception as e:
        print("Photon API failed, falling back to Nominatim. Error:", e)

    # 2. Fallback to Nominatim API
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 10,
                "countrycodes": "in",
                "addressdetails": 1,
            },
            headers=headers,
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data:
            try:
                address = item.get("address", {})
                name = address.get("amenity") or address.get("road") or address.get("suburb") or item.get("display_name", "").split(",")[0]
                city = address.get("city") or address.get("town") or address.get("village") or ""
                state = address.get("state", "")
                country = address.get("country", "")

                results.append({
                    "display_name": item.get("display_name", ""),
                    "name": name,
                    "city": city,
                    "state": state,
                    "country": country,
                    "latitude": float(item.get("lat")),
                    "longitude": float(item.get("lon")),
                })
            except (TypeError, ValueError, KeyError):
                continue
        return jsonify(_dedupe_locations(results))
    except Exception as e:
        print("Nominatim API failed. Error:", e)
        return jsonify([])


@home_bp.route("/api/stations/near")
def stations_near_api():
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
        radius = float(request.args.get("radius", 10.0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates or radius"}), 400

    nearby = get_stations_near_coords(lat, lng, radius)
    return jsonify(nearby)


@home_bp.route("/api/iot/status", methods=["POST"])
def update_iot_status():
    from database.db import db
    data = request.get_json() or {}
    charger_id = data.get("charger_id")
    status_str = data.get("status")

    if not charger_id or not status_str:
        return jsonify({"error": "charger_id and status are required"}), 400

    from models.charger import Charger, ChargerStatus
    from services.charger_service import get_charger

    charger = get_charger(charger_id)
    if not charger:
        return jsonify({"error": "Charger not found"}), 404

    try:
        new_status = ChargerStatus(status_str)
        charger.status = new_status

        from services.iot_service import save_iot_data
        save_iot_data({
            "charger_id": charger_id,
            "current": data.get("current", 0.0),
            "voltage": data.get("voltage", 230.0),
            "power": data.get("power", 0.0),
            "temperature": data.get("temperature", 25.0),
            "charger_status": new_status,
        })

        db.session.commit()
        return jsonify({"success": True, "message": "Charger status updated successfully", "status": charger.status.value})
    except ValueError:
        return jsonify({"error": f"Invalid status: {status_str}"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to save IoT telemetry: {str(e)}"}), 500


@home_bp.route("/api/recommend", methods=["POST"])
def get_route_recommendation():
    import json
    from datetime import datetime, timedelta
    from models.booking import Booking, BookingStatus
    from models.charger import Charger, ChargerStatus
    
    data = request.get_json() or {}
    route_coords = data.get("route_coords", []) # List of [lat, lon]
    vehicle_type = data.get("vehicle_type", "Car")
    battery_percent = float(data.get("battery_percent", 80.0))
    remaining_range = float(data.get("remaining_range", 150.0))
    total_duration = float(data.get("total_duration", 0.0)) # in seconds
    total_distance = float(data.get("total_distance", 0.0)) # in meters
    dest_lat = float(data.get("dest_lat", 0.0))
    dest_lon = float(data.get("dest_lon", 0.0))

    if not route_coords:
        return jsonify({"error": "route_coords is required"}), 400

    # Get active stations
    stations = get_all_stations()
    active_stations = [s for s in stations if s.status == "Active" and s.latitude is not None and s.longitude is not None]

    analyzed_stations = []

    # Parse current time
    now_dt = datetime.now()
    now_time = now_dt.time()

    for idx, station in enumerate(active_stations):
        # Calculate min distance to route path
        min_dist_m = 9999999.0
        closest_coord_idx = 0
        for i, coord in enumerate(route_coords):
            dist_m = calculate_distance_meters(station.latitude, station.longitude, coord[0], coord[1])
            if dist_m < min_dist_m:
                min_dist_m = dist_m
                closest_coord_idx = i

        dist_km = min_dist_m / 1000.0

        # Filter: within 2km of route path OR within 5km of destination coordinates
        dist_to_dest = calculate_distance_meters(station.latitude, station.longitude, dest_lat, dest_lon) / 1000.0
        is_near_route = dist_km <= 2.0
        is_near_dest = dist_to_dest <= 5.0

        if not is_near_route and not is_near_dest:
            continue

        # Analyze Chargers
        chargers = station.chargers
        total_chargers = len(chargers)
        available_chargers = 0
        busy_chargers = 0
        offline_chargers = 0
        reserved_chargers = 0
        connector_types = set()
        max_power = 0.0

        for charger in chargers:
            connector_types.add(charger.connector_type)
            if charger.power_kw and float(charger.power_kw) > max_power:
                max_power = float(charger.power_kw)

            # Check status
            st_val = charger.status.value.lower()
            if st_val == "available":
                available_chargers += 1
            elif st_val == "busy":
                busy_chargers += 1
            elif st_val in ["offline", "maintenance"]:
                offline_chargers += 1
            elif st_val == "reserved":
                reserved_chargers += 1

        # Calculate estimated waiting time
        waiting_time = 0
        if available_chargers == 0 and total_chargers > 0:
            # Query active bookings ending soonest
            overlapping_bookings = Booking.query.filter(
                Booking.station_id == station.station_id,
                Booking.booking_date == now_dt.date(),
                Booking.booking_start_time <= now_time,
                Booking.booking_end_time > now_time,
                Booking.booking_status.in_([BookingStatus.CONFIRMED, BookingStatus.CHARGING])
            ).all()

            if overlapping_bookings:
                min_wait = 9999
                for b in overlapping_bookings:
                    b_end_dt = datetime.combine(now_dt.date(), b.booking_end_time)
                    diff_mins = (b_end_dt - now_dt).total_seconds() / 60.0
                    if 0 < diff_mins < min_wait:
                        min_wait = int(diff_mins)
                waiting_time = min_wait if min_wait != 9999 else 15
            else:
                waiting_time = 15

        # Estimated arrival time details
        route_fraction = closest_coord_idx / len(route_coords) if len(route_coords) > 0 else 1.0
        eta_minutes = int((total_duration / 60.0) * route_fraction)
        station_distance_km = route_fraction * (total_distance / 1000.0)
        
        arrival_dt = now_dt + timedelta(minutes=eta_minutes)
        eta_str = arrival_dt.strftime("%I:%M %p")

        # Scores (out of 100)
        # Availability Score (max 25)
        avail_score = 0
        if available_chargers > 0:
            avail_score = 25
        elif busy_chargers > 0:
            avail_score = 10

        # Waiting Time Score (max 25)
        wait_score = 25
        if waiting_time > 0:
            wait_score = max(5, int(25 - (waiting_time / 2.0)))

        # Distance Score (max 20)
        dist_score = 5
        if dist_km <= 0.5:
            dist_score = 20
        elif dist_km <= 1.0:
            dist_score = 15
        elif dist_km <= 2.0:
            dist_score = 10

        # Cost Score (max 15)
        cost_score = 15
        price_val = float(station.price_per_kwh or 15.0)
        if price_val > 12:
            cost_score = max(5, int(15 - (price_val - 12) * 1.5))

        # Battery Safety Score (max 15)
        battery_score = 10
        if battery_percent < 20 or remaining_range < station_distance_km:
            if remaining_range < station_distance_km:
                battery_score = 0
            else:
                battery_score = 15

        total_score = avail_score + wait_score + dist_score + cost_score + battery_score

        analyzed_stations.append({
            "station_id": station.station_id,
            "first_charger_id": chargers[0].charger_id if chargers else station.station_id,
            "station_name": station.station_name,
            "city": station.city,
            "address": station.address,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "price_per_kwh": float(station.price_per_kwh or 15.0),
            "image_url": station.image_url or "",
            "connector_types": list(connector_types),
            "max_power": max_power,
            "total_chargers": total_chargers,
            "available_chargers": available_chargers,
            "busy_chargers": busy_chargers,
            "offline_chargers": offline_chargers,
            "reserved_chargers": reserved_chargers,
            "waiting_time": waiting_time,
            "dist_km": round(dist_km, 2),
            "station_distance_km": round(station_distance_km, 2),
            "eta_minutes": eta_minutes,
            "eta_str": eta_str,
            "avail_score": avail_score,
            "wait_score": wait_score,
            "dist_score": dist_score,
            "cost_score": cost_score,
            "battery_score": battery_score,
            "total_score": total_score,
            "travel_order": closest_coord_idx
        })

    analyzed_stations.sort(key=lambda x: x["travel_order"])

    recommended = None
    nearest_busy = None
    alternative = None
    reason = "No charging stations found near the route."

    if analyzed_stations:
        if battery_percent < 20:
            reachable_stations = [s for s in analyzed_stations if s["station_distance_km"] <= remaining_range and s["available_chargers"] + s["busy_chargers"] > 0]
            if reachable_stations:
                recommended = reachable_stations[0]
                reason = f"Battery level is low ({battery_percent}%). Recommending the nearest compatible station immediately for safety."
        
        if not recommended:
            nearest = analyzed_stations[0]
            if nearest["available_chargers"] > 0:
                recommended = nearest
                reason = "Nearest station is available with good charger availability and low travel detour."
            elif nearest["waiting_time"] < nearest["eta_minutes"]:
                recommended = nearest
                reason = f"Nearest station is busy, but the estimated waiting time ({nearest['waiting_time']} mins) is less than your travel time ({nearest['eta_minutes']} mins). The charger will likely be available upon arrival."
            else:
                nearest_busy = nearest
                next_available = [s for s in analyzed_stations[1:] if s["available_chargers"] > 0]
                if next_available:
                    recommended = next_available[0]
                    reason = f"Nearest station is currently busy with a high wait time of {nearest['waiting_time']} minutes. Recommending the next station ahead which has active available chargers."
                else:
                    highest_scored = max(analyzed_stations, key=lambda x: x["total_score"])
                    recommended = highest_scored
                    reason = "Recommended based on optimal charger availability, lowest waiting time, competitive charging cost, and minimal detour."

        alts = [s for s in analyzed_stations if s["station_id"] != recommended["station_id"]]
        if alts:
            alts.sort(key=lambda x: x["total_score"], reverse=True)
            alternative = alts[0]

    return jsonify({
        "recommended_station": recommended,
        "nearest_busy_station": nearest_busy,
        "alternative_station": alternative,
        "reason": reason,
        "all_stations": analyzed_stations
    })




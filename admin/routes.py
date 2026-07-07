from datetime import date
from datetime import datetime
from decimal import Decimal
from decimal import InvalidOperation
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from database.db import db
from models.booking import Booking
from models.charger import Charger, ChargerStatus
from models.payment import Payment, PaymentStatus
from models.station import Station
from services.station_service import (
    create_station,
    delete_station,
    get_all_stations,
    get_station_by_id,
    search_station,
    station_address_exists,
    station_coordinates_exist,
    station_to_admin_dict,
    update_station,
    is_station_exact_duplicate,
)
from services.geocoding_service import build_station_search_address, get_station_coordinates
from services.charger_service import (
    VALID_CHARGER_STATUSES,
    VALID_VEHICLE_TYPES,
    charger_name_exists,
    charger_to_admin_dict,
    create_charger,
    delete_charger,
    get_charger,
    search_chargers,
    update_charger,
)
from services.connector_type_service import (
    VALID_VEHICLE_TYPES as CONNECTOR_VEHICLE_TYPES,
    connector_name_exists,
    connector_to_admin_dict,
    create_connector_type,
    delete_connector_type,
    get_active_connector_types,
    get_all_connector_types,
    get_connector_type,
    parse_power,
    update_connector_type,
)


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
def auto_update_statuses():
    from services.charger_service import update_charger_statuses
    update_charger_statuses()


ALLOWED_STATION_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
STATION_STATUSES = ["Active", "Inactive"]
CHARGER_VEHICLES = ["Car", "Bike", "Car + Bike"]
CHARGER_STATUSES = ["Available", "Busy", "Offline", "Maintenance"]
CONNECTOR_STATUSES = ["Active", "Inactive"]


def admin_required(view_func):
    """Protect admin routes with a session login check."""

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login", next=request.path))

        return view_func(*args, **kwargs)

    return wrapped_view


@admin_bp.route("/")
def admin_index():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin.dashboard"))

    return redirect(url_for("admin.login"))


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember_me = request.form.get("remember_me") == "on"

        error = validate_login(username, password)

        if error:
            flash(error, "danger")
            return render_template("admin/login.html", username=username)

        session.clear()
        session["admin_logged_in"] = True
        session["admin_username"] = username
        session.permanent = remember_me

        return redirect(request.args.get("next") or url_for("admin.dashboard"))

    return render_template("admin/login.html", username="")


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    return render_template(
        "admin/dashboard.html",
        active_page="dashboard",
        stats=get_dashboard_stats(),
        system_status=get_system_status(),
        current_date=date.today().strftime("%d %b %Y"),
    )


@admin_bp.route("/stations")
@admin_required
def stations():
    search_query = (request.args.get("q", "") or "").strip()
    status_filter = request.args.get("status", "All") or "All"
    stations_list = search_station(search_query, status_filter)

    return render_template(
        "admin/stations/list.html",
        active_page="stations",
        current_date=date.today().strftime("%d %b %Y"),
        search_query=search_query,
        status_filter=status_filter,
        stations=[station_to_admin_dict(station) for station in stations_list],
    )


@admin_bp.route("/stations/add", methods=["GET", "POST"])
@admin_required
def add_station():
    if request.method == "POST":
        data, errors = build_station_payload(request.form, request.files)
        selected_connector_ids = parse_selected_connector_ids(request.form)

        if not errors:
            image_path = save_station_image(request.files.get("image"))

            if image_path:
                data["image_url"] = image_path

            station = create_station(data)

            if station:
                sync_station_chargers(station.station_id, selected_connector_ids)
                flash("Station added successfully.", "success")
                return redirect(url_for("admin.stations"))

            errors.append("Station could not be saved. Please try again.")

        return render_station_form(
            "Add Station",
            "admin.add_station",
            errors,
            request.form,
            selected_connector_ids=selected_connector_ids,
        )

    return render_station_form("Add Station", "admin.add_station")


@admin_bp.route("/stations/edit/<int:station_id>", methods=["GET", "POST"])
@admin_required
def edit_station(station_id):
    station = get_station_by_id(station_id)

    if station is None:
        flash("Station not found.", "danger")
        return redirect(url_for("admin.stations"))

    if request.method == "POST":
        data, errors = build_station_payload(
            request.form,
            request.files,
            current_station_id=station.station_id,
        )
        selected_connector_ids = parse_selected_connector_ids(request.form)

        if not errors:
            image_path = save_station_image(request.files.get("image"))

            if image_path:
                data["image_url"] = image_path

            updated_station = update_station(station.station_id, data)

            if updated_station:
                sync_station_chargers(station.station_id, selected_connector_ids)
                flash("Station updated successfully.", "success")
                return redirect(url_for("admin.stations"))

            errors.append("Station could not be updated. Please try again.")

        return render_station_form(
            "Edit Station",
            "admin.edit_station",
            errors,
            request.form,
            station,
            selected_connector_ids=selected_connector_ids,
        )

    return render_station_form("Edit Station", "admin.edit_station", station=station)


@admin_bp.route("/stations/delete/<int:station_id>", methods=["POST"])
@admin_required
def delete_station_route(station_id):
    success, message = delete_station(station_id)
    flash(message, "success" if success else "danger")
    return redirect(url_for("admin.stations"))


@admin_bp.route("/stations/geocode", methods=["POST"])
@admin_required
def geocode_station_address():
    payload = request.get_json(silent=True) or {}
    station_name = (payload.get("station_name") or "").strip()
    city = (payload.get("city") or "").strip()
    address = (payload.get("address") or "").strip()
    current_station_id = parse_integer(payload.get("station_id"))

    if not station_name or not city or not address:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Station name, city, and complete address are required.",
                }
            ),
            400,
        )

    if station_address_exists(address, current_station_id):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "A charging station already exists at this address.",
                }
            ),
            409,
        )

    search_address = build_station_search_address(station_name, city, address)
    coordinates = get_station_coordinates(station_name, city, address)

    if coordinates is None:
        return (
            jsonify(
                {
                    "success": False,
                    "message": (
                        "Unable to locate this address. "
                        "Please enter a more complete address."
                    ),
                }
            ),
            404,
        )

    if station_coordinates_exist(
        coordinates["latitude"],
        coordinates["longitude"],
        current_station_id,
    ):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "A charging station already exists at this location.",
                }
            ),
            409,
        )

    return jsonify(
        {
            "success": True,
            "message": "Location Found Successfully",
            "latitude": str(coordinates["latitude"]),
            "longitude": str(coordinates["longitude"]),
            "display_name": coordinates["display_name"],
            "search_address": coordinates.get("search_address", search_address),
        }
    )


@admin_bp.route("/chargers")
@admin_required
def chargers():
    search_query = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "All")
    connector_filter = request.args.get("connector", "All")
    station_filter = request.args.get("station_id", type=int)
    connector_options = get_all_connector_types()
    charger_list = search_chargers(
        search_query,
        status_filter,
        connector_filter,
    )

    if station_filter:
        charger_list = [
            charger for charger in charger_list if charger.station_id == station_filter
        ]

    return render_template(
        "admin/chargers/list.html",
        active_page="chargers",
        chargers=[charger_to_admin_dict(charger) for charger in charger_list],
        connector_filter=connector_filter,
        connectors=[connector.connector_name for connector in connector_options],
        current_date=date.today().strftime("%d %b %Y"),
        search_query=search_query,
        station_filter=station_filter,
        stations=get_all_stations(),
        status_filter=status_filter,
        statuses=CHARGER_STATUSES,
    )


@admin_bp.route("/connectors")
@admin_required
def connectors():
    connectors_list = get_all_connector_types()

    return render_template(
        "admin/connectors/list.html",
        active_page="connectors",
        connectors=[connector_to_admin_dict(connector) for connector in connectors_list],
        current_date=date.today().strftime("%d %b %Y"),
    )


@admin_bp.route("/connectors/add", methods=["GET", "POST"])
@admin_required
def add_connector():
    if request.method == "POST":
        data, errors = build_connector_payload(request.form)

        if not errors:
            connector = create_connector_type(data)

            if connector:
                flash("Connector type added successfully.", "success")
                return redirect(url_for("admin.connectors"))

            errors.append("Connector type could not be saved. Please try again.")

        return render_connector_form("Add Connector", errors, request.form)

    return render_connector_form("Add Connector")


@admin_bp.route("/connectors/edit/<int:connector_id>", methods=["GET", "POST"])
@admin_required
def edit_connector(connector_id):
    connector = get_connector_type(connector_id)

    if connector is None:
        flash("Connector type not found.", "danger")
        return redirect(url_for("admin.connectors"))

    if request.method == "POST":
        data, errors = build_connector_payload(
            request.form,
            current_connector_id=connector.id,
        )

        if not errors:
            updated_connector = update_connector_type(connector.id, data)

            if updated_connector:
                flash("Connector type updated successfully.", "success")
                return redirect(url_for("admin.connectors"))

            errors.append("Connector type could not be updated. Please try again.")

        return render_connector_form(
            "Edit Connector",
            errors,
            request.form,
            connector,
        )

    return render_connector_form("Edit Connector", connector=connector)


@admin_bp.route("/connectors/delete/<int:connector_id>", methods=["POST"])
@admin_required
def delete_connector_route(connector_id):
    success, message = delete_connector_type(connector_id)
    flash(message, "success" if success else "danger")
    return redirect(url_for("admin.connectors"))


@admin_bp.route("/chargers/add", methods=["GET", "POST"])
@admin_required
def add_charger():
    stations_list = get_all_stations()
    connector_list = get_active_connector_types()
    selected_station_id = request.args.get("station_id", type=int)

    if request.method == "POST":
        data, errors = build_charger_payload(request.form)

        if not stations_list:
            errors.append("Add a station before creating chargers.")

        if not connector_list:
            errors.append("Add an active connector type before creating chargers.")

        if not errors:
            charger = create_charger(data)

            if charger:
                flash("Charger added successfully.", "success")
                return redirect(url_for("admin.chargers", station_id=charger.station_id))

            errors.append("Charger could not be saved. Please try again.")

        return render_charger_form(
            "Add Charger",
            errors,
            request.form,
            stations_list=stations_list,
            connector_list=connector_list,
        )

    return render_charger_form(
        "Add Charger",
        stations_list=stations_list,
        connector_list=connector_list,
        selected_station_id=selected_station_id,
    )


@admin_bp.route("/chargers/edit/<int:charger_id>", methods=["GET", "POST"])
@admin_required
def edit_charger(charger_id):
    charger = get_charger(charger_id)

    if charger is None:
        flash("Charger not found.", "danger")
        return redirect(url_for("admin.chargers"))

    stations_list = get_all_stations()
    connector_list = get_active_connector_types()

    if request.method == "POST":
        data, errors = build_charger_payload(
            request.form,
            current_charger_id=charger.charger_id,
        )

        if not errors:
            updated_charger = update_charger(charger.charger_id, data)

            if updated_charger:
                flash("Charger updated successfully.", "success")
                return redirect(url_for("admin.chargers"))

            errors.append("Charger could not be updated. Please try again.")

        return render_charger_form(
            "Edit Charger",
            errors,
            request.form,
            charger,
            stations_list,
            connector_list=connector_list,
        )

    return render_charger_form(
        "Edit Charger",
        charger=charger,
        stations_list=stations_list,
        connector_list=connector_list,
    )


@admin_bp.route("/chargers/delete/<int:charger_id>", methods=["POST"])
@admin_required
def delete_charger_route(charger_id):
    success, message = delete_charger(charger_id)
    flash(message, "success" if success else "danger")
    return redirect(url_for("admin.chargers"))


@admin_bp.route("/bookings")
@admin_required
def bookings():
    from models.booking import Booking
    from models.station import Station
    
    search_query = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "All")
    
    query = Booking.query.join(Station)
    
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Booking.user_mobile.ilike(search_pattern),
                Station.station_name.ilike(search_pattern)
            )
        )
        
    if status_filter != "All":
        from models.booking import BookingStatus
        try:
            query = query.filter(Booking.booking_status == BookingStatus(status_filter))
        except ValueError:
            pass
            
    bookings_list = query.order_by(Booking.booking_date.desc(), Booking.booking_start_time.desc()).all()
    
    from models.booking import BookingStatus
    statuses = [s.value for s in BookingStatus]
    
    return render_template(
        "admin/bookings/list.html",
        active_page="bookings",
        bookings=[b.to_dict() for b in bookings_list],
        bookings_detail=[{
            "booking_id": b.booking_id,
            "user_mobile": b.user_mobile,
            "station_name": b.station.station_name if b.station else "Unknown",
            "charger_name": b.charger.charger_name if b.charger else "Unknown",
            "booking_date": b.booking_date.strftime("%d %b %Y") if b.booking_date else "",
            "time_range": f"{b.booking_start_time.strftime('%I:%M %p')} - {b.booking_end_time.strftime('%I:%M %p')}" if b.booking_start_time and b.booking_end_time else "",
            "booking_status": b.booking_status.value if b.booking_status else "",
        } for b in bookings_list],
        search_query=search_query,
        status_filter=status_filter,
        statuses=statuses,
        current_date=date.today().strftime("%d %b %Y"),
    )


@admin_bp.route("/bookings/cancel/<int:booking_id>", methods=["POST"])
@admin_required
def cancel_booking(booking_id):
    from models.booking import Booking, BookingStatus
    from services.charger_service import update_charger_statuses
    
    booking = db.session.get(Booking, booking_id)
    if booking:
        booking.booking_status = BookingStatus.CANCELLED
        db.session.flush()
        update_charger_statuses()
        db.session.commit()
        flash("Booking cancelled successfully.", "success")
    else:
        flash("Booking not found.", "danger")
    return redirect(request.referrer or url_for("admin.bookings"))


@admin_bp.route("/bookings/complete/<int:booking_id>", methods=["POST"])
@admin_required
def complete_booking(booking_id):
    from models.booking import Booking, BookingStatus
    from services.charger_service import update_charger_statuses
    
    booking = db.session.get(Booking, booking_id)
    if booking:
        booking.booking_status = BookingStatus.COMPLETED
        db.session.flush()
        update_charger_statuses()
        db.session.commit()
        flash("Booking completed successfully.", "success")
    else:
        flash("Booking not found.", "danger")
    return redirect(request.referrer or url_for("admin.bookings"))


@admin_bp.route("/chargers/status/<int:charger_id>", methods=["POST"])
@admin_required
def update_charger_status_route(charger_id):
    from models.charger import Charger, ChargerStatus
    from services.charger_service import get_charger
    
    status_str = request.form.get("status")
    charger = get_charger(charger_id)
    if not charger:
        flash("Charger not found.", "danger")
        return redirect(url_for("admin.chargers"))
        
    try:
        new_status = ChargerStatus(status_str)
        charger.status = new_status
        db.session.commit()
        flash(f"Charger status updated to {status_str} successfully.", "success")
    except ValueError:
        flash("Invalid status value.", "danger")
        
    return redirect(request.referrer or url_for("admin.chargers"))


@admin_bp.route("/chargers/bookings/<int:charger_id>")
@admin_required
def charger_bookings(charger_id):
    from models.charger import Charger
    from models.booking import Booking, BookingStatus
    
    charger = db.session.get(Charger, charger_id)
    if not charger:
        flash("Charger not found.", "danger")
        return redirect(url_for("admin.chargers"))
        
    now = datetime.now()
    today = now.date()
    curr_time = now.time()
    
    current_booking = Booking.query.filter(
        Booking.charger_id == charger_id,
        Booking.booking_date == today,
        Booking.booking_start_time <= curr_time,
        Booking.booking_end_time >= curr_time,
        Booking.booking_status.in_([BookingStatus.CONFIRMED, BookingStatus.CHARGING])
    ).first()
    
    next_booking = Booking.query.filter(
        Booking.charger_id == charger_id,
        db.or_(
            Booking.booking_date > today,
            db.and_(Booking.booking_date == today, Booking.booking_start_time > curr_time)
        ),
        Booking.booking_status.in_([BookingStatus.CONFIRMED, BookingStatus.CHARGING])
    ).order_by(Booking.booking_date.asc(), Booking.booking_start_time.asc()).first()
    
    history_bookings = Booking.query.filter(
        Booking.charger_id == charger_id
    ).order_by(Booking.booking_date.desc(), Booking.booking_start_time.desc()).all()
    
    return render_template(
        "admin/chargers/bookings.html",
        active_page="chargers",
        charger=charger,
        current_booking=current_booking,
        next_booking=next_booking,
        history_bookings=history_bookings,
        current_date=date.today().strftime("%d %b %Y"),
    )


@admin_bp.route("/payments")
@admin_required
def payments():
    from models.payment import Payment
    from database.db import db
    
    payments_list = Payment.query.order_by(Payment.created_at.desc()).all()
    
    # Calculate revenue
    total_revenue = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0))
                          .filter(Payment.payment_status.value == "Success")
                          .scalar() or 0)
                          
    return render_template(
        "admin/payments/list.html",
        active_page="payments",
        payments=payments_list,
        total_revenue=total_revenue,
        current_date=date.today().strftime("%d %b %Y")
    )


@admin_bp.route("/iot")
@admin_required
def iot():
    return render_placeholder("IoT Monitoring", "iot", "bi-cpu")


@admin_bp.route("/settings")
@admin_required
def settings():
    return render_placeholder("Settings", "settings", "bi-gear")


@admin_bp.route("/logout")
@admin_required
def logout():
    session.clear()
    flash("Admin session closed successfully.", "success")
    return redirect(url_for("admin.login"))


def validate_login(username, password):
    if not username or not password:
        return "Username and password are required."

    configured_username = current_app.config.get("ADMIN_USERNAME")
    configured_password = current_app.config.get("ADMIN_PASSWORD")

    if not configured_username or not configured_password:
        return "Admin credentials are not configured."

    if username != configured_username:
        return "Invalid username."

    if not check_password_hash(configured_password, password):
        return "Invalid password."

    return None


def get_dashboard_stats():
    from models.booking import Booking, BookingStatus
    from models.payment import Payment, PaymentStatus
    
    today = date.today()
    
    # Upcoming reservations count
    upcoming_count = 0
    try:
        upcoming_count = Booking.query.filter(
            Booking.booking_date >= today,
            Booking.booking_status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.CHARGING])
        ).count()
    except Exception:
        db.session.rollback()
        
    # Completed sessions count
    completed_count = 0
    try:
        completed_count = Booking.query.filter(
            Booking.booking_status == BookingStatus.COMPLETED
        ).count()
    except Exception:
        db.session.rollback()
        
    # Cancelled sessions count
    cancelled_count = 0
    try:
        cancelled_count = Booking.query.filter(
            Booking.booking_status == BookingStatus.CANCELLED
        ).count()
    except Exception:
        db.session.rollback()
        
    # Total revenue count
    total_rev = 0.0
    try:
        total_rev = float(db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0))
                          .filter(Payment.payment_status == PaymentStatus.SUCCESS)
                          .scalar() or 0)
    except Exception:
        db.session.rollback()

    return {
        "total_stations": safe_count(Station),
        "total_chargers": safe_count(Charger),
        "todays_bookings": safe_count_today_bookings(),
        "todays_revenue": safe_today_revenue(),
        "upcoming_reservations": upcoming_count,
        "completed_sessions": completed_count,
        "cancelled_sessions": cancelled_count,
        "total_revenue": total_rev,
    }


def get_system_status():
    database_connected = check_database_connection()

    return [
        {
            "label": "Database",
            "value": "Connected" if database_connected else "Offline",
        },
        {"label": "Backend", "value": "Running"},
        {
            "label": "PostgreSQL",
            "value": "Connected" if database_connected else "Unavailable",
        },
        {
            "label": "Application",
            "value": "Healthy" if database_connected else "Limited",
        },
    ]


def safe_count(model):
    try:
        return model.query.count()
    except SQLAlchemyError:
        db.session.rollback()
        return 0


def safe_count_today_bookings():
    try:
        return Booking.query.filter(Booking.booking_date == date.today()).count()
    except SQLAlchemyError:
        db.session.rollback()
        return 0


def safe_today_revenue():
    try:
        total = (
            db.session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.payment_status == PaymentStatus.SUCCESS)
            .filter(func.date(Payment.payment_time) == date.today())
            .scalar()
        )
        return float(total or 0)
    except SQLAlchemyError:
        db.session.rollback()
        return 0


def check_database_connection():
    try:
        db.session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        db.session.rollback()
        return False


def render_placeholder(title, active_page, icon):
    return render_template(
        "admin/placeholder.html",
        active_page=active_page,
        current_date=date.today().strftime("%d %b %Y"),
        icon=icon,
        title=title,
    )


def build_station_payload(form, files, current_station_id=None):
    errors = []
    station_name = form.get("station_name", "").strip()
    city = form.get("city", "").strip()
    address = form.get("address", "").strip()
    description = form.get("description", "").strip()
    status = form.get("status", "").strip()
    is_open_24_hours = form.get("is_open_24_hours") == "on"

    price_per_kwh = parse_decimal(form.get("price_per_kwh"))
    opening_time = parse_time(form.get("opening_time")) if not is_open_24_hours else parse_time("00:00")
    closing_time = parse_time(form.get("closing_time")) if not is_open_24_hours else parse_time("23:59")
    existing_station = get_station_by_id(current_station_id) if current_station_id else None

    if not station_name:
        errors.append("Station name is required.")

    if not city:
        errors.append("City is required.")

    if not address:
        errors.append("Address is required.")

    if price_per_kwh is None or price_per_kwh <= Decimal("0"):
        errors.append("Price per kWh must be greater than 0.")

    if not is_open_24_hours and opening_time is None:
        errors.append("Opening time is required.")

    if not is_open_24_hours and closing_time is None:
        errors.append("Closing time is required.")

    if status not in STATION_STATUSES:
        errors.append("Status must be Active or Inactive.")

    image = files.get("image") if files else None

    if image and image.filename and not is_allowed_station_image(image.filename):
        errors.append("Station image must be jpg, jpeg, png, or webp.")

    latitude = parse_coordinate(form.get("latitude"))
    longitude = parse_coordinate(form.get("longitude"))
    display_name = (form.get("display_name") or "").strip() or None

    if not errors:
        if can_reuse_existing_coordinates(existing_station, station_name, city, address):
            latitude = existing_station.latitude
            longitude = existing_station.longitude
            display_name = existing_station.display_name
        elif latitude is not None and longitude is not None:
            # Use verified coordinates from the admin geocode preview when available.
            display_name = display_name or None
        else:
            coordinates = get_station_coordinates(station_name, city, address)

            if coordinates is None:
                errors.append(
                    "Unable to find this address. Please enter a more complete unique address."
                )
            else:
                latitude = coordinates["latitude"]
                longitude = coordinates["longitude"]
                display_name = coordinates["display_name"]

        if (
            latitude is not None
            and longitude is not None
            and is_station_exact_duplicate(station_name, address, latitude, longitude, current_station_id)
        ):
            errors.append("A charging station with the exact same name, address, and coordinates already exists.")

    data = {
        "station_name": station_name,
        "city": city,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "display_name": display_name,
        "description": description or None,
        "price_per_kwh": price_per_kwh,
        "is_open_24_hours": is_open_24_hours,
        "opening_time": opening_time,
        "closing_time": closing_time,
        "status": status,
    }

    return data, errors


def can_reuse_existing_coordinates(station, station_name, city, address):
    if station is None:
        return False

    return (
        station.station_name == station_name
        and station.city == city
        and station.address == address
        and station.latitude is not None
        and station.longitude is not None
    )


def parse_decimal(value):
    try:
        return Decimal((value or "").strip())
    except (InvalidOperation, AttributeError):
        return None


def parse_coordinate(value):
    coordinate = parse_decimal(value)

    if coordinate is None:
        return None

    return coordinate.quantize(Decimal("0.000001"))


def parse_time(value):
    try:
        return datetime.strptime((value or "").strip(), "%H:%M").time()
    except ValueError:
        return None


def is_allowed_station_image(filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return extension in ALLOWED_STATION_IMAGE_EXTENSIONS


def save_station_image(image):
    if not image or not image.filename:
        return None

    filename = secure_filename(image.filename)

    if not filename or not is_allowed_station_image(filename):
        return None

    extension = filename.rsplit(".", 1)[-1].lower()
    upload_dir = Path(current_app.root_path) / "static" / "uploads" / "stations"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}.{extension}"
    image.save(upload_dir / stored_filename)

    return f"uploads/stations/{stored_filename}"


def render_station_form(
    title,
    endpoint,
    errors=None,
    form_data=None,
    station=None,
    selected_connector_ids=None,
):
    if selected_connector_ids is None:
        selected_connector_ids = get_station_selected_connector_ids(station)

    return render_template(
        "admin/stations/form.html",
        active_page="stations",
        current_date=date.today().strftime("%d %b %Y"),
        endpoint=endpoint,
        errors=errors or [],
        form_data=form_data,
        connectors=get_active_connector_types(),
        selected_connector_ids=selected_connector_ids,
        station=station,
        statuses=STATION_STATUSES,
        title=title,
    )


def parse_selected_connector_ids(form):
    connector_ids = []

    for value in form.getlist("connector_type_ids"):
        connector_id = parse_integer(value)

        if connector_id is not None:
            connector_ids.append(connector_id)

    return connector_ids


def get_station_selected_connector_ids(station):
    if station is None:
        return []

    return [
        charger.connector_type_id
        for charger in station.chargers
        if charger.connector_type_id is not None
    ]


def sync_station_chargers(station_id, selected_connector_ids):
    existing_chargers = Charger.query.filter_by(station_id=station_id).all()
    existing_connector_ids = {c.connector_type_id for c in existing_chargers if c.connector_type_id is not None}

    # Add chargers for newly checked connectors
    for connector_id in selected_connector_ids:
        if connector_id not in existing_connector_ids:
            connector = get_connector_type(connector_id)
            if connector and connector.is_active:
                create_charger({
                    "station_id": station_id,
                    "charger_name": f"{connector.connector_name} Charger",
                    "connector_type_id": connector.id,
                    "connector_type": connector.connector_name,
                    "power_kw": connector.default_power_kw,
                    "vehicle_type": connector.vehicle_type,
                    "status": ChargerStatus.AVAILABLE,
                    "iot_enabled": False,
                })

    # Remove chargers for unchecked connectors
    for charger in existing_chargers:
        if charger.connector_type_id not in selected_connector_ids:
            db.session.delete(charger)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


def build_charger_payload(form, current_charger_id=None):
    errors = []
    station_id = parse_integer(form.get("station_id"))
    connector_id = parse_integer(form.get("connector_type_id"))
    connector = get_connector_type(connector_id)
    charger_name = form.get("charger_name", "").strip()
    power_kw = parse_decimal(form.get("power_kw"))
    status = form.get("status", "").strip()
    iot_enabled = form.get("iot_enabled") == "on"

    if station_id is None or get_station_by_id(station_id) is None:
        errors.append("Station is required.")

    if not charger_name:
        errors.append("Charger name is required.")
    elif station_id and charger_name_exists(
        station_id,
        charger_name,
        current_charger_id,
    ):
        errors.append("Charger name already exists for this station.")

    if connector is None or not connector.is_active:
        errors.append("Connector type is required.")

    if power_kw is None or power_kw <= Decimal("0"):
        errors.append("Power must be greater than zero.")

    if status not in VALID_CHARGER_STATUSES:
        errors.append("Status is required.")

    data = {
        "station_id": station_id,
        "charger_name": charger_name,
        "connector_type_id": connector.id if connector else None,
        "connector_type": connector.connector_name if connector else "",
        "power_kw": power_kw,
        "vehicle_type": connector.vehicle_type if connector else "",
        "status": ChargerStatus(status) if status in VALID_CHARGER_STATUSES else None,
        "iot_enabled": iot_enabled,
    }

    return data, errors


def parse_integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_connector_payload(form, current_connector_id=None):
    errors = []
    connector_name = form.get("connector_name", "").strip()
    vehicle_type = form.get("vehicle_type", "").strip()
    default_power_kw = parse_power(form.get("default_power_kw"))
    status = form.get("status", "Active").strip()

    if not connector_name:
        errors.append("Connector name is required.")
    elif connector_name_exists(connector_name, current_connector_id):
        errors.append("Connector name already exists.")

    if vehicle_type not in CONNECTOR_VEHICLE_TYPES:
        errors.append("Vehicle type is required.")

    if default_power_kw is None or default_power_kw <= Decimal("0"):
        errors.append("Default power must be greater than zero.")

    if status not in CONNECTOR_STATUSES:
        errors.append("Status must be Active or Inactive.")

    return (
        {
            "connector_name": connector_name,
            "vehicle_type": vehicle_type,
            "default_power_kw": default_power_kw,
            "is_active": status == "Active",
        },
        errors,
    )


def render_connector_form(title, errors=None, form_data=None, connector=None):
    return render_template(
        "admin/connectors/form.html",
        active_page="connectors",
        connector=connector,
        current_date=date.today().strftime("%d %b %Y"),
        errors=errors or [],
        form_data=form_data,
        statuses=CONNECTOR_STATUSES,
        title=title,
        vehicles=CHARGER_VEHICLES,
    )


def render_charger_form(
    title,
    errors=None,
    form_data=None,
    charger=None,
    stations_list=None,
    connector_list=None,
    selected_station_id=None,
):
    return render_template(
        "admin/chargers/form.html",
        active_page="chargers",
        charger=charger,
        connectors=connector_list or [],
        current_date=date.today().strftime("%d %b %Y"),
        errors=errors or [],
        form_data=form_data,
        selected_station_id=selected_station_id,
        stations=stations_list or [],
        statuses=CHARGER_STATUSES,
        title=title,
        vehicles=CHARGER_VEHICLES,
    )

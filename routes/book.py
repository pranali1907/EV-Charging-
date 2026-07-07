import re
from datetime import datetime, timedelta
from random import SystemRandom

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from services.charger_service import get_charger
from services.guest_service import verify_guest
from services.station_service import get_station_by_id, station_to_discovery_dict


book_bp = Blueprint("book", __name__, url_prefix="/book")


@book_bp.before_request
def auto_update_statuses():
    from services.charger_service import update_charger_statuses
    update_charger_statuses()


INDIAN_MOBILE_PATTERN = re.compile(r"^[6-9]\d{9}$")
OTP_PATTERN = re.compile(r"^\d{6}$")
OTP_EXPIRY_MINUTES = 5


@book_bp.route("/verify")
def verify():
    station_id = request.args.get("station_id", type=int)
    charger_id = request.args.get("charger_id", type=int)
    station = get_station_by_id(station_id) if station_id else None
    charger = get_selected_charger(station_id, charger_id)

    if station is None:
        flash("Please select a valid charging station before booking.", "danger")
        return redirect(url_for("home.index"))

    if charger is None:
        flash("Please select a valid charger before booking.", "warning")
        return redirect(url_for("home.station_details", station_id=station.station_id))

    session["booking_station_id"] = station.station_id
    session["booking_charger_id"] = charger.charger_id

    return render_template(
        "book_verify.html",
        station=station_to_discovery_dict(station),
        charger=charger.to_dict(),
        mobile_number=session.get("guest_otp", {}).get("mobile_number", ""),
    )


@book_bp.route("/send-otp", methods=["POST"])
def send_otp():
    station_id = request.form.get("station_id", type=int) or session.get(
        "booking_station_id"
    )
    charger_id = request.form.get("charger_id", type=int) or session.get(
        "booking_charger_id"
    )
    mobile_number = normalize_mobile(request.form.get("mobile_number"))

    if get_station_by_id(station_id) is None or get_selected_charger(
        station_id,
        charger_id,
    ) is None:
        flash("Please select a valid charger before requesting OTP.", "danger")
        return redirect(url_for("home.index"))

    if not is_valid_mobile(mobile_number):
        flash("Enter a valid Indian mobile number with exactly 10 digits.", "danger")
        return redirect(url_for("book.verify", station_id=station_id, charger_id=charger_id))

    otp = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    session["booking_station_id"] = station_id
    session["guest_otp"] = {
        "mobile_number": mobile_number,
        "otp": otp,
        "expires_at": expires_at.isoformat(),
    }
    session.pop("verified_guest_id", None)
    session["booking_charger_id"] = charger_id

    flash(f"Demo OTP sent successfully. Use {otp} to continue.", "success")
    return redirect(url_for("book.verify", station_id=station_id, charger_id=charger_id))


@book_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    station_id = request.form.get("station_id", type=int) or session.get(
        "booking_station_id"
    )
    charger_id = request.form.get("charger_id", type=int) or session.get(
        "booking_charger_id"
    )
    mobile_number = normalize_mobile(request.form.get("mobile_number"))
    otp = (request.form.get("otp") or "").strip()

    if get_station_by_id(station_id) is None or get_selected_charger(
        station_id,
        charger_id,
    ) is None:
        flash("Please select a valid charger before verifying OTP.", "danger")
        return redirect(url_for("home.index"))

    if not is_valid_mobile(mobile_number):
        flash("Enter a valid Indian mobile number with exactly 10 digits.", "danger")
        return redirect(url_for("book.verify", station_id=station_id, charger_id=charger_id))

    if not OTP_PATTERN.fullmatch(otp):
        flash("OTP must be exactly 6 digits.", "danger")
        return redirect(url_for("book.verify", station_id=station_id, charger_id=charger_id))

    otp_data = session.get("guest_otp")

    if not otp_data or otp_data.get("mobile_number") != mobile_number:
        flash("Please request a fresh OTP for this mobile number.", "warning")
        return redirect(url_for("book.verify", station_id=station_id, charger_id=charger_id))

    if is_otp_expired(otp_data.get("expires_at")):
        session.pop("guest_otp", None)
        flash("Your OTP has expired. Please request a new OTP.", "danger")
        return redirect(url_for("book.verify", station_id=station_id, charger_id=charger_id))

    if otp_data.get("otp") != otp:
        flash("The OTP entered is incorrect. Please check and try again.", "danger")
        return redirect(url_for("book.verify", station_id=station_id, charger_id=charger_id))

    guest = verify_guest(mobile_number)

    if guest is None:
        flash("We could not verify your guest profile right now. Please try again.", "danger")
        return redirect(url_for("book.verify", station_id=station_id, charger_id=charger_id))

    session["verified_guest_id"] = guest.guest_id
    session["verified_guest_mobile"] = guest.mobile_number
    session["booking_station_id"] = station_id
    session["booking_charger_id"] = charger_id
    session.pop("guest_otp", None)

    flash("Mobile number verified successfully. You can now continue booking.", "success")
    return redirect(url_for("book.booking_form", station_id=station_id, charger_id=charger_id))


@book_bp.route("/form")
def booking_form():
    station_id = request.args.get("station_id", type=int) or session.get(
        "booking_station_id"
    )
    charger_id = request.args.get("charger_id", type=int) or session.get(
        "booking_charger_id"
    )
    station = get_station_by_id(station_id) if station_id else None
    charger = get_selected_charger(station_id, charger_id)
    guest_id = session.get("verified_guest_id")

    if station is None or charger is None:
        flash("Please select a valid charger before booking.", "danger")
        return redirect(url_for("home.index"))

    if not guest_id:
        flash("Please verify your mobile number before opening the booking form.", "warning")
        return redirect(url_for("book.verify", station_id=station_id, charger_id=charger_id))

    return render_template(
        "booking_form.html",
        station=station_to_discovery_dict(station),
        charger=charger.to_dict(),
        mobile_number=session.get("verified_guest_mobile", ""),
    )


def normalize_mobile(mobile_number):
    return re.sub(r"\D", "", mobile_number or "")


def is_valid_mobile(mobile_number):
    return bool(INDIAN_MOBILE_PATTERN.fullmatch(mobile_number or ""))


def generate_otp():
    return f"{SystemRandom().randint(100000, 999999)}"


def is_otp_expired(expires_at):
    try:
        return datetime.utcnow() > datetime.fromisoformat(expires_at)
    except (TypeError, ValueError):
        return True


def get_selected_charger(station_id, charger_id):
    charger = get_charger(charger_id)

    if charger is None or charger.station_id != station_id:
        return None

    return charger


def generate_time_slots():
    slots = []
    # 06:00 to 22:30 in 30-minute intervals
    h, m = 6, 0
    while h < 22 or (h == 22 and m <= 30):
        slots.append(f"{h:02d}:{m:02d}")
        m += 30
        if m >= 60:
            h += 1
            m = 0
    return slots


def validate_booking_request(station_id, charger_id, booking_date_str, booking_time_str, duration_mins=60):
    from models.booking import Booking, BookingStatus
    errors = []

    if not station_id or not charger_id or not booking_date_str or not booking_time_str:
        return None, ["All fields (Station, Charger, Date, Time) are required."]

    station = get_station_by_id(station_id)
    if not station or station.status != "Active":
        errors.append("Selected station does not exist or is inactive.")

    charger = get_charger(charger_id)
    if not charger or charger.station_id != station_id:
        errors.append("Selected charger does not exist at this station.")
    elif charger.status.value in ["Offline", "Maintenance"]:
        errors.append("Selected charger is offline or under maintenance.")

    connector = None
    if charger:
        connector = charger.connector
        if not connector or not connector.is_active:
            errors.append("Selected charger's connector is not active.")

    booking_date = None
    try:
        booking_date = datetime.strptime(booking_date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        if booking_date < today:
            errors.append("Booking date cannot be in the past.")
    except ValueError:
        errors.append("Invalid booking date format. Use YYYY-MM-DD.")

    booking_time = None
    try:
        # Parse time from 12-hour AM/PM format (e.g. "10:15 AM", "01:30 PM", "10:15AM")
        t_str = booking_time_str.strip().upper()
        match = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", t_str)
        if not match:
            raise ValueError()
        h, m, ampm = match.groups()
        h = int(h)
        m = int(m)
        if h < 1 or h > 12 or m < 0 or m > 59:
            raise ValueError()
            
        time_str_parsed = f"{h:02d}:{m:02d} {ampm}"
        booking_time = datetime.strptime(time_str_parsed, "%I:%M %p").time()
        
        today = datetime.now().date()
        if booking_date and booking_date == today:
            current_time = datetime.now().time()
            if booking_time <= current_time:
                errors.append("Cannot book a past time slot for today.")
    except ValueError:
        errors.append("Invalid time format. Please use hh:mm AM/PM format (e.g., 10:15 AM).")

    if errors:
        return None, errors

    # Calculate end time using datetime combine
    booking_end = (datetime.combine(booking_date, booking_time) + timedelta(minutes=duration_mins)).time()

    existing_booking = Booking.query.filter(
        Booking.charger_id == charger_id,
        Booking.booking_date == booking_date,
        Booking.booking_status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.CHARGING, BookingStatus.COMPLETED]),
        Booking.booking_start_time < booking_end,
        Booking.booking_end_time > booking_time
    ).first()

    if existing_booking:
        errors.append("This charger is already booked during the selected time.")

    if errors:
        return None, errors

    return {
        "station_id": station_id,
        "charger_id": charger_id,
        "connector_id": connector.id if connector else None,
        "booking_date": booking_date,
        "booking_time": booking_time,
        "booking_start_time": booking_time,
        "booking_end_time": booking_end
    }, []


@book_bp.route("/api/slots")
def get_available_slots():
    from flask import jsonify
    charger_id = request.args.get("charger_id", type=int)
    date_str = request.args.get("date")

    if not charger_id or not date_str:
        return jsonify({"error": "charger_id and date parameters are required"}), 400

    try:
        booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    all_slots = generate_time_slots()
    today = datetime.now().date()
    current_time = datetime.now().time()

    from models.booking import Booking, BookingStatus
    active_bookings = Booking.query.filter(
        Booking.charger_id == charger_id,
        Booking.booking_date == booking_date,
        Booking.booking_status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.CHARGING, BookingStatus.COMPLETED])
    ).all()

    booked_starts = {b.booking_start_time.strftime("%H:%M") for b in active_bookings}

    slots_data = []
    for slot in all_slots:
        available = True
        reason = None

        if slot in booked_starts:
            available = False
            reason = "Already Booked"
        elif booking_date < today:
            available = False
            reason = "Past Date"
        elif booking_date == today:
            slot_time = datetime.strptime(slot, "%H:%M").time()
            if slot_time <= current_time:
                available = False
                reason = "Past Time"

        slots_data.append({
            "time": slot,
            "available": available,
            "reason": reason
        })

    return jsonify(slots_data)


@book_bp.route("/submit", methods=["POST"])
def submit_booking():
    station_id = request.form.get("station_id", type=int)
    charger_id = request.form.get("charger_id", type=int)
    booking_date_str = request.form.get("booking_date")
    booking_time_str = request.form.get("booking_time")
    duration_mins = request.form.get("booking_duration", type=int, default=60)

    guest_id = session.get("verified_guest_id")
    user_mobile = session.get("verified_guest_mobile")
    if not guest_id or not user_mobile:
        flash("Your verification session has expired. Please verify your mobile number again.", "danger")
        return redirect(url_for("home.index"))

    validated_payload, errors = validate_booking_request(station_id, charger_id, booking_date_str, booking_time_str, duration_mins)

    if errors:
        for err in errors:
            flash(err, "danger")
        return redirect(url_for("book.booking_form", station_id=station_id, charger_id=charger_id))

    from database.db import db
    from models.booking import Booking, BookingStatus

    try:
        # Calculate Estimated metrics
        charger = get_charger(charger_id)
        station = get_station_by_id(station_id)
        
        energy_kwh = float(charger.power_kw) * (duration_mins / 60.0)
        estimated_cost = energy_kwh * float(station.price_per_kwh)

        booking = Booking(
            guest_id=guest_id,
            station_id=station_id,
            charger_id=charger_id,
            connector_id=validated_payload["connector_id"],
            user_mobile=user_mobile,
            booking_date=validated_payload["booking_date"],
            booking_time=validated_payload["booking_time"],
            booking_start_time=validated_payload["booking_start_time"],
            booking_end_time=validated_payload["booking_end_time"],
            booking_status=BookingStatus.PENDING,  # Remains PENDING until payment completes
            booking_token_amount=estimated_cost
        )
        db.session.add(booking)
        db.session.commit()

        # Redirect to demo payment page!
        return redirect(url_for("book.payment_page", booking_id=booking.booking_id))

    except Exception as e:
        db.session.rollback()
        flash(f"Failed to create booking: {str(e)}", "danger")
        return redirect(url_for("book.booking_form", station_id=station_id, charger_id=charger_id))


@book_bp.route("/payment/<int:booking_id>")
def payment_page(booking_id):
    from models.booking import Booking
    booking = Booking.query.get_or_404(booking_id)
    
    # Calculate duration
    start_delta = timedelta(hours=booking.booking_start_time.hour, minutes=booking.booking_start_time.minute)
    end_delta = timedelta(hours=booking.booking_end_time.hour, minutes=booking.booking_end_time.minute)
    duration_mins = int((end_delta - start_delta).total_seconds() / 60)
    
    energy_kwh = float(booking.charger.power_kw) * (duration_mins / 60.0)
    
    return render_template(
        "demo_payment.html",
        booking=booking,
        station=booking.station,
        charger=booking.charger,
        duration_mins=duration_mins,
        energy_kwh=energy_kwh,
        estimated_cost=booking.booking_token_amount,
        csrf_token=session.get("csrf_token")
    )


@book_bp.route("/payment/confirm/<int:booking_id>", methods=["POST"])
def confirm_payment(booking_id):
    from flask import jsonify
    from database.db import db
    from models.booking import Booking, BookingStatus
    from models.payment import Payment, PaymentStatus
    
    booking = Booking.query.get_or_404(booking_id)
    payment_method = request.form.get("payment_method") or request.json.get("payment_method")
    
    if not payment_method:
        return jsonify({"error": "Payment method is required"}), 400
        
    try:
        # 1. Update Booking status to CONFIRMED
        booking.booking_status = BookingStatus.CONFIRMED
        
        # 2. Update Charger status to BUSY if active right now
        from services.charger_service import update_charger_statuses
        update_charger_statuses()
        
        # 3. Generate Transaction ID (TXN + YYYYMMDD + padded booking_id)
        txn_date = datetime.now().strftime("%Y%m%d")
        transaction_id = f"TXN{txn_date}{booking.booking_id:04d}"
        
        # 4. Create Payment table record
        # PaymentStatus: PENDING for Cash, SUCCESS for other methods
        p_status = PaymentStatus.PENDING if payment_method == "Cash at Station" else PaymentStatus.SUCCESS
        
        payment = Payment(
            booking_id=booking.booking_id,
            payment_type=payment_method,
            payment_method=payment_method,
            transaction_id=transaction_id,
            amount=booking.booking_token_amount,
            payment_status=p_status,
            payment_time=datetime.utcnow(),
            payment_date=datetime.utcnow()
        )
        db.session.add(payment)
        db.session.commit()
        
        flash("Payment completed successfully! Your booking is confirmed.", "success")
        return jsonify({
            "success": True,
            "redirect_url": url_for("book.receipt_page", booking_id=booking.booking_id)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Payment processing failed: {str(e)}"}), 500


@book_bp.route("/receipt/<int:booking_id>")
def receipt_page(booking_id):
    from models.booking import Booking
    booking = Booking.query.get_or_404(booking_id)
    payment = booking.payment
    
    # Calculate duration
    start_delta = timedelta(hours=booking.booking_start_time.hour, minutes=booking.booking_start_time.minute)
    end_delta = timedelta(hours=booking.booking_end_time.hour, minutes=booking.booking_end_time.minute)
    duration_mins = int((end_delta - start_delta).total_seconds() / 60)
    
    energy_kwh = float(booking.charger.power_kw) * (duration_mins / 60.0)
    
    # Invoice Number: INV-YYYY-padded_booking_id
    invoice_number = f"INV-{datetime.now().strftime('%Y')}-{booking.booking_id:06d}"
    
    return render_template(
        "receipt.html",
        booking=booking,
        payment=payment,
        duration_mins=duration_mins,
        energy_kwh=energy_kwh,
        invoice_number=invoice_number
    )


@book_bp.route("/history")
def booking_history():
    from models.booking import Booking
    user_mobile = session.get("verified_guest_mobile")
    if not user_mobile:
        session["booking_return_url"] = url_for("book.booking_history")
        flash("Please verify your mobile number to view booking history.", "info")
        return redirect(url_for("book.verify"))
        
    bookings_list = Booking.query.filter_by(user_mobile=user_mobile).order_by(Booking.booking_date.desc(), Booking.booking_start_time.desc()).all()
    
    # Separate them by category for display
    today = datetime.now().date()
    now_time = datetime.now().time()
    
    categorized_bookings = []
    for b in bookings_list:
        # Calculate duration
        start_delta = timedelta(hours=b.booking_start_time.hour, minutes=b.booking_start_time.minute)
        end_delta = timedelta(hours=b.booking_end_time.hour, minutes=b.booking_end_time.minute)
        duration_mins = int((end_delta - start_delta).total_seconds() / 60)
        
        energy_kwh = float(b.charger.power_kw) * (duration_mins / 60.0)
        
        status_category = "Upcoming"
        if b.booking_status.value == "Cancelled":
            status_category = "Cancelled"
        elif b.booking_status.value == "Completed":
            status_category = "Completed"
        elif b.booking_date < today or (b.booking_date == today and b.booking_end_time < now_time):
            status_category = "Completed"
            
        categorized_bookings.append({
            "booking": b,
            "duration_mins": duration_mins,
            "energy_kwh": energy_kwh,
            "status_category": status_category
        })
        
    return render_template(
        "booking_history.html",
        bookings=categorized_bookings,
        user_mobile=user_mobile
    )

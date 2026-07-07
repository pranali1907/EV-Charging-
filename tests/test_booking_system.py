import pytest
from datetime import datetime, date, time, timedelta
from app import app
from database.db import db
from models.station import Station
from models.charger import Charger, ChargerStatus
from models.connector_type import ConnectorType
from models.booking import Booking, BookingStatus
from models.guest_user import GuestUser
from models.payment import Payment, PaymentStatus
from routes.book import generate_time_slots, validate_booking_request

def clean_test_db_remnants():
    try:
        # Clean up stations, connectors, guests, payments, bookings matching test names
        names = ["Test Station Booking", "Test Station Auto Update", "Test Station IoT", "Payment Test Station", "Pune Station A", "Pune Station B"]
        for name in names:
            station = Station.query.filter_by(station_name=name).first()
            if station:
                # Delete related bookings
                Booking.query.filter_by(station_id=station.station_id).delete(synchronize_session=False)
                # Delete related chargers
                Charger.query.filter_by(station_id=station.station_id).delete(synchronize_session=False)
                db.session.delete(station)
                
        connector_names = ["CCS2 Test type", "CCS2 Test type 2", "CCS2 Test type 3", "CCS2 Payment Test", "CCS2 recommendation test"]
        for cname in connector_names:
            conn = ConnectorType.query.filter_by(connector_name=cname).first()
            if conn:
                Charger.query.filter_by(connector_type_id=conn.id).delete(synchronize_session=False)
                db.session.delete(conn)

        mobiles = ["9988776655", "9988776644", "9988776633"]
        for mob in mobiles:
            # Delete payments related to bookings of this mobile
            db.session.query(Payment).filter(Payment.booking_id.in_(
                db.session.query(Booking.booking_id).filter_by(user_mobile=mob)
            )).delete(synchronize_session=False)
            Booking.query.filter_by(user_mobile=mob).delete(synchronize_session=False)
            GuestUser.query.filter_by(mobile_number=mob).delete(synchronize_session=False)
            
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Pre-clean error:", e)

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with app.app_context():
            clean_test_db_remnants()
            yield client

def test_generate_time_slots(client):
    slots = generate_time_slots()
    assert isinstance(slots, list)
    assert "06:00" in slots
    assert "22:30" in slots
    assert "05:30" not in slots
    assert "23:00" not in slots
    assert len(slots) == 34  # 6:00 to 22:30 is 16.5 hours = 33 intervals + 1 = 34 slots

def test_booking_validation_and_duplicate(client):
    # Setup test data
    station = Station(
        station_name="Test Station Booking",
        city="Pune",
        address="Kothrud, Pune",
        latitude=18.5204,
        longitude=73.8567,
        status="Active",
        price_per_kwh=15.0,
        is_open_24_hours=True,
        opening_time=time(0, 0),
        closing_time=time(23, 59)
    )
    db.session.add(station)
    db.session.flush()

    connector = ConnectorType(
        connector_name="CCS2 Test type",
        vehicle_type="Car",
        default_power_kw=50.0,
        is_active=True
    )
    db.session.add(connector)
    db.session.flush()

    charger = Charger(
        station_id=station.station_id,
        charger_name="Test Charger A",
        connector_type_id=connector.id,
        connector_type=connector.connector_name,
        power_kw=50.0,
        vehicle_type="Car",
        status=ChargerStatus.AVAILABLE
    )
    db.session.add(charger)
    db.session.flush()

    guest = GuestUser(
        full_name="Booking Tester",
        mobile_number="9988776655",
        vehicle_number="MH-12-AB-1234"
    )
    db.session.add(guest)
    db.session.flush()

    db.session.commit()

    # Let's validate a valid booking request for tomorrow at 10:00 AM
    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    payload, errors = validate_booking_request(station.station_id, charger.charger_id, tomorrow_str, "10:00 AM", 30)
    assert not errors
    assert payload["station_id"] == station.station_id
    assert payload["charger_id"] == charger.charger_id
    assert payload["connector_id"] == connector.id
    assert payload["booking_start_time"] == time(10, 0)
    assert payload["booking_end_time"] == time(10, 30)

    # Test invalid time formats
    _, err_fmt = validate_booking_request(station.station_id, charger.charger_id, tomorrow_str, "10:00", 30)
    assert err_fmt
    assert "Invalid time format" in err_fmt[0]

    _, err_fmt2 = validate_booking_request(station.station_id, charger.charger_id, tomorrow_str, "10:00 XM", 30)
    assert err_fmt2
    assert "Invalid time format" in err_fmt2[0]

    # Test past time on today
    today_str = date.today().strftime("%Y-%m-%d")
    ten_mins_ago = (datetime.now() - timedelta(minutes=10)).strftime("%I:%M %p")
    _, err_past = validate_booking_request(station.station_id, charger.charger_id, today_str, ten_mins_ago, 30)
    assert err_past
    assert "Cannot book a past time slot for today" in err_past[0]

    # Test future time on today (10 minutes from now)
    ten_mins_hence = (datetime.now() + timedelta(minutes=10)).strftime("%I:%M %p")
    payload_future, errors_future = validate_booking_request(station.station_id, charger.charger_id, today_str, ten_mins_hence, 30)
    assert not errors_future or "already booked" in errors_future[0]

    # Create the booking in DB
    booking = Booking(
        guest_id=guest.guest_id,
        station_id=station.station_id,
        charger_id=charger.charger_id,
        connector_id=connector.id,
        user_mobile=guest.mobile_number,
        booking_date=payload["booking_date"],
        booking_time=payload["booking_time"],
        booking_start_time=payload["booking_start_time"],
        booking_end_time=payload["booking_end_time"],
        booking_status=BookingStatus.CONFIRMED,
        booking_token_amount=0.0
    )
    db.session.add(booking)
    db.session.commit()

    # Try validating the exact same booking (should fail as duplicate/overlap)
    payload2, errors2 = validate_booking_request(station.station_id, charger.charger_id, tomorrow_str, "10:00 AM", 30)
    assert errors2
    assert errors2[0] == "This charger is already booked during the selected time."

    # Clean up
    db.session.delete(booking)
    db.session.delete(guest)
    db.session.delete(charger)
    db.session.delete(connector)
    db.session.delete(station)
    db.session.commit()

def test_booking_status_auto_update(client):
    # Setup test data
    station = Station(
        station_name="Test Station Auto Update",
        city="Mumbai",
        address="Bandra, Mumbai",
        latitude=19.0760,
        longitude=72.8777,
        status="Active",
        price_per_kwh=18.0,
        is_open_24_hours=True,
        opening_time=time(0, 0),
        closing_time=time(23, 59)
    )
    db.session.add(station)
    db.session.flush()

    connector = ConnectorType(
        connector_name="CCS2 Test type 2",
        vehicle_type="Car",
        default_power_kw=50.0,
        is_active=True
    )
    db.session.add(connector)
    db.session.flush()

    charger = Charger(
        station_id=station.station_id,
        charger_name="Test Charger B",
        connector_type_id=connector.id,
        connector_type=connector.connector_name,
        power_kw=50.0,
        vehicle_type="Car",
        status=ChargerStatus.AVAILABLE
    )
    db.session.add(charger)
    db.session.flush()

    guest = GuestUser(
        full_name="Booking Tester 2",
        mobile_number="9988776644",
        vehicle_number="MH-02-CD-5678"
    )
    db.session.add(guest)
    db.session.flush()

    db.session.commit()

    # Set booking start time to 15 mins ago and end time to 15 mins from now
    now = datetime.now()
    start_dt = now - timedelta(minutes=15)
    end_dt = now + timedelta(minutes=15)

    booking = Booking(
        guest_id=guest.guest_id,
        station_id=station.station_id,
        charger_id=charger.charger_id,
        connector_id=connector.id,
        user_mobile=guest.mobile_number,
        booking_date=now.date(),
        booking_time=start_dt.time(),
        booking_start_time=start_dt.time(),
        booking_end_time=end_dt.time(),
        booking_status=BookingStatus.CONFIRMED,
        booking_token_amount=0.0
    )
    db.session.add(booking)
    db.session.commit()

    # Run automatic status updates
    from services.charger_service import update_charger_statuses
    update_charger_statuses()

    # Check charger status is BUSY
    updated_charger = db.session.get(Charger, charger.charger_id)
    assert updated_charger.status == ChargerStatus.BUSY

    # Change booking times to the past
    past_start = now - timedelta(hours=2)
    past_end = now - timedelta(hours=1, minutes=30)
    booking.booking_start_time = past_start.time()
    booking.booking_end_time = past_end.time()
    db.session.commit()

    # Run auto status update again
    update_charger_statuses()

    # Check charger status is AVAILABLE again
    updated_charger = db.session.get(Charger, charger.charger_id)
    assert updated_charger.status == ChargerStatus.AVAILABLE

    # Clean up
    db.session.delete(booking)
    db.session.delete(guest)
    db.session.delete(charger)
    db.session.delete(connector)
    db.session.delete(station)
    db.session.commit()

def test_iot_status_update(client):
    # Setup test data
    station = Station(
        station_name="Test Station IoT",
        city="Mumbai",
        address="Bandra, Mumbai",
        latitude=19.0760,
        longitude=72.8777,
        status="Active",
        price_per_kwh=18.0,
        is_open_24_hours=True,
        opening_time=time(0, 0),
        closing_time=time(23, 59)
    )
    db.session.add(station)
    db.session.flush()

    connector = ConnectorType(
        connector_name="CCS2 Test type 3",
        vehicle_type="Car",
        default_power_kw=50.0,
        is_active=True
    )
    db.session.add(connector)
    db.session.flush()

    charger = Charger(
        station_id=station.station_id,
        charger_name="Test Charger IoT",
        connector_type_id=connector.id,
        connector_type=connector.connector_name,
        power_kw=50.0,
        vehicle_type="Car",
        status=ChargerStatus.AVAILABLE
    )
    db.session.add(charger)
    db.session.commit()

    # Send POST request to IoT API
    response = client.post("/api/iot/status", json={
        "charger_id": charger.charger_id,
        "status": "Busy",
        "current": 16.5,
        "voltage": 230.1,
        "power": 3.8,
        "temperature": 32.5
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["status"] == "Busy"

    # Check charger status is BUSY in DB
    db.session.refresh(charger)
    assert charger.status == ChargerStatus.BUSY

    # Verify IoT record is saved
    from models.iot_data import IoTData
    iot_record = IoTData.query.filter_by(charger_id=charger.charger_id).first()
    assert iot_record is not None
    assert float(iot_record.current) == 16.5
    assert float(iot_record.voltage) == 230.1
    assert float(iot_record.power) == 3.8
    assert float(iot_record.temperature) == 32.5

    # Clean up
    db.session.delete(iot_record)
    db.session.delete(charger)
    db.session.delete(connector)
    db.session.delete(station)
    db.session.commit()

def test_booking_metrics_and_payment_flow(client):
    # Setup test data
    station = Station(
        station_name="Payment Test Station",
        city="Mumbai",
        address="Lower Parel, Mumbai",
        latitude=19.0123,
        longitude=72.8456,
        status="Active",
        price_per_kwh=17.99,
        is_open_24_hours=True,
        opening_time=time(0, 0),
        closing_time=time(23, 59)
    )
    db.session.add(station)
    db.session.flush()

    connector = ConnectorType(
        connector_name="CCS2 Payment Test",
        vehicle_type="Car",
        default_power_kw=60.0,
        is_active=True
    )
    db.session.add(connector)
    db.session.flush()

    charger = Charger(
        station_id=station.station_id,
        charger_name="60kW CCS2 Charger",
        connector_type_id=connector.id,
        connector_type=connector.connector_name,
        power_kw=60.0,
        vehicle_type="Car",
        status=ChargerStatus.AVAILABLE
    )
    db.session.add(charger)
    db.session.flush()

    guest = GuestUser(
        full_name="Payment Tester",
        mobile_number="9988776633",
        vehicle_number="MH-01-EE-9999"
    )
    db.session.add(guest)
    db.session.flush()
    db.session.commit()

    # 1. Test calculation logic: 60kW charger, 60 minutes duration @ 17.99 price per kWh
    duration_mins = 60
    energy_kwh = float(charger.power_kw) * (duration_mins / 60.0)
    estimated_cost = energy_kwh * float(station.price_per_kwh)
    
    assert energy_kwh == 60.0
    assert round(estimated_cost, 2) == 1079.40

    # 2. Test booking submission resulting in PENDING status & redirecting to payment screen
    with client.session_transaction() as sess:
        sess["verified_guest_id"] = guest.guest_id
        sess["verified_guest_mobile"] = guest.mobile_number

    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    submit_response = client.post("/book/submit", data={
        "station_id": station.station_id,
        "charger_id": charger.charger_id,
        "booking_date": tomorrow_str,
        "booking_time": "12:00 PM",
        "booking_duration": "60"
    })
    
    assert submit_response.status_code == 302
    
    # Verify booking in DB is pending
    booking = Booking.query.filter_by(guest_id=guest.guest_id).first()
    assert booking is not None
    assert booking.booking_status == BookingStatus.PENDING
    assert round(float(booking.booking_token_amount), 2) == 1079.40

    # 3. Test payment confirm API (UPI payment)
    confirm_response = client.post(f"/book/payment/confirm/{booking.booking_id}", json={
        "payment_method": "UPI"
    })
    
    assert confirm_response.status_code == 200
    data = confirm_response.get_json()
    assert data["success"] is True
    
    # Verify booking status changed to Confirmed
    db.session.refresh(booking)
    assert booking.booking_status == BookingStatus.CONFIRMED
    
    # Verify payment record created in DB
    from models.payment import Payment, PaymentStatus
    payment = Payment.query.filter_by(booking_id=booking.booking_id).first()
    assert payment is not None
    assert payment.payment_method == "UPI"
    assert round(float(payment.amount), 2) == 1079.40
    assert payment.payment_status == PaymentStatus.SUCCESS
    assert payment.transaction_id.startswith("TXN")

    # 4. Verify receipt page renders correctly
    receipt_response = client.get(f"/book/receipt/{booking.booking_id}")
    assert receipt_response.status_code == 200
    assert b"PAID RECEIPT" in receipt_response.data
    assert b"60.00 kWh" in receipt_response.data
    assert b"1079.40" in receipt_response.data

    # 5. Verify history page lists bookings
    history_response = client.get("/book/history")
    assert history_response.status_code == 200
    assert b"60kW CCS2 Charger" in history_response.data

    # 6. Verify admin dashboard statistics include upcoming count & total revenue
    from admin.routes import get_dashboard_stats
    stats = get_dashboard_stats()
    assert stats["upcoming_reservations"] >= 1
    assert stats["total_revenue"] >= 1079.40

    # Clean up
    db.session.delete(payment)
    db.session.delete(booking)
    db.session.delete(guest)
    db.session.delete(charger)
    db.session.delete(connector)
    db.session.delete(station)
    db.session.commit()

def test_ai_smart_recommendation(client):
    # Setup test data
    stationA = Station(
        station_name="Pune Station A",
        city="Pune",
        address="Bhavdhan, Pune",
        latitude=18.5130,
        longitude=73.7740,
        status="Active",
        price_per_kwh=14.0,
        is_open_24_hours=True,
        opening_time=time(0, 0),
        closing_time=time(23, 59)
    )
    db.session.add(stationA)
    
    stationB = Station(
        station_name="Pune Station B",
        city="Pune",
        address="Kothrud, Pune",
        latitude=18.5070,
        longitude=73.8050,
        status="Active",
        price_per_kwh=12.0,
        is_open_24_hours=True,
        opening_time=time(0, 0),
        closing_time=time(23, 59)
    )
    db.session.add(stationB)
    db.session.flush()

    connector = ConnectorType(
        connector_name="CCS2 recommendation test",
        vehicle_type="Car",
        default_power_kw=50.0,
        is_active=True
    )
    db.session.add(connector)
    db.session.flush()

    guest = GuestUser(
        full_name="Recommendation Tester",
        mobile_number="9988776655",
        vehicle_number="MH-12-AB-1111"
    )
    db.session.add(guest)
    db.session.flush()

    chargerA = Charger(
        station_id=stationA.station_id,
        charger_name="Charger A1",
        connector_type_id=connector.id,
        connector_type=connector.connector_name,
        power_kw=50.0,
        vehicle_type="Car",
        status=ChargerStatus.BUSY
    )
    db.session.add(chargerA)

    chargerB = Charger(
        station_id=stationB.station_id,
        charger_name="Charger B1",
        connector_type_id=connector.id,
        connector_type=connector.connector_name,
        power_kw=50.0,
        vehicle_type="Car",
        status=ChargerStatus.AVAILABLE
    )
    db.session.add(chargerB)
    db.session.flush()

    # Create active booking today for charger A to prevent auto-reverting status to Available
    now_dt = datetime.now()
    active_booking_A = Booking(
        guest_id=guest.guest_id,
        station_id=stationA.station_id,
        charger_id=chargerA.charger_id,
        connector_id=connector.id,
        user_mobile="9988776655",
        booking_date=now_dt.date(),
        booking_time=now_dt.time(),
        booking_start_time=(now_dt - timedelta(minutes=10)).time(),
        booking_end_time=(now_dt + timedelta(minutes=30)).time(),
        booking_status=BookingStatus.CONFIRMED,
        booking_token_amount=0.0
    )
    db.session.add(active_booking_A)
    db.session.commit()

    route_coords = [
        [18.5150, 73.7650],
        [18.5130, 73.7740],
        [18.5100, 73.7900],
        [18.5070, 73.8050],
        [18.5050, 73.8200]
    ]

    payload = {
        "route_coords": route_coords,
        "vehicle_type": "Car",
        "battery_percent": 80.0,
        "remaining_range": 150.0,
        "total_duration": 600.0,
        "total_distance": 5000.0,
        "dest_lat": 18.5050,
        "dest_lon": 73.8200
    }

    # Scenario 3: Busy charger nearest, recommend alternative Station B
    response = client.post("/api/recommend", json=payload)
    assert response.status_code == 200
    res_data = response.get_json()

    rec = res_data["recommended_station"]
    assert rec is not None
    assert rec["station_name"] == "Pune Station B"
    assert "busy" in res_data["reason"].lower()

    # Scenario 4: Low battery safety check (< 20%) -> recommend nearest compatible immediately
    payload["battery_percent"] = 15.0
    
    # Remove active booking so charger A can be evaluated as available/busy safely
    db.session.delete(active_booking_A)
    chargerA.status = ChargerStatus.AVAILABLE
    db.session.commit()

    response2 = client.post("/api/recommend", json=payload)
    res_data2 = response2.get_json()
    rec2 = res_data2["recommended_station"]
    assert rec2 is not None
    assert rec2["station_name"] == "Pune Station A"
    assert "low" in res_data2["reason"].lower()

    # Clean up
    db.session.delete(chargerA)
    db.session.delete(chargerB)
    db.session.delete(connector)
    db.session.delete(guest)
    db.session.delete(stationA)
    db.session.delete(stationB)
    db.session.commit()

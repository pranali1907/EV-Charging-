from types import SimpleNamespace

from app import app


def test_add_station_redirects_to_station_list(monkeypatch):
    monkeypatch.setattr(
        "admin.routes.build_station_payload",
        lambda form, files, current_station_id=None: (
            {
                "station_name": "Flow Test Station",
                "city": "Pune",
                "address": "Test Address 123",
                "description": "",
                "price_per_kwh": "0.25",
                "is_open_24_hours": False,
                "opening_time": "09:00",
                "closing_time": "21:00",
                "status": "Active",
            },
            [],
        ),
    )
    monkeypatch.setattr("admin.routes.save_station_image", lambda image: None)
    monkeypatch.setattr(
        "admin.routes.create_station",
        lambda data: SimpleNamespace(station_id=999),
    )
    monkeypatch.setattr(
        "admin.routes.sync_station_chargers",
        lambda station_id, selected_connector_ids: None,
    )

    client = app.test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True
        session["admin_username"] = "admin"

    response = client.post(
        "/admin/stations/add",
        data={
            "station_name": "Flow Test Station",
            "city": "Pune",
            "address": "Test Address 123",
            "description": "",
            "price_per_kwh": "0.25",
            "opening_time": "09:00",
            "closing_time": "21:00",
            "status": "Active",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/stations")

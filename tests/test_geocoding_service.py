import pytest

from services import geocoding_service


def test_get_station_coordinates_falls_back_to_city_when_address_is_not_found(monkeypatch):
    captured_searches = []

    def fake_get_coordinates(full_address):
        captured_searches.append(full_address)
        if full_address == "kolhapur, Maharashtra, India":
            return {
                "latitude": 1,
                "longitude": 2,
                "display_name": "City Center",
            }
        return None

    monkeypatch.setattr(geocoding_service, "get_coordinates", fake_get_coordinates)

    coords = geocoding_service.get_station_coordinates(
        "E-Fill Electric Charging Station",
        "kolhapur",
        "Chandran Menon Rd, Shahu Market Yard, Kolhapur, Maharashtra 416005, India",
    )

    assert coords == {
        "latitude": 1,
        "longitude": 2,
        "display_name": "City Center",
        "search_address": "kolhapur, Maharashtra, India",
    }
    assert captured_searches == [
        "Chandran Menon Rd, Shahu Market Yard, Kolhapur, Maharashtra 416005, India",
        "Maharashtra 416005, India, kolhapur",
        "Kolhapur, Maharashtra 416005, India",
        "E-Fill Electric Charging Station, Chandran Menon Rd, Shahu Market Yard, Kolhapur, Maharashtra 416005, India",
        "kolhapur, Maharashtra, India",
    ]


def test_get_station_coordinates_falls_back_to_city_when_address_is_invalid(monkeypatch):
    captured_searches = []

    def fake_get_coordinates(full_address):
        captured_searches.append(full_address)
        return None

    monkeypatch.setattr(geocoding_service, "get_coordinates", fake_get_coordinates)

    coords = geocoding_service.get_station_coordinates(
        "Test Station",
        "kolhapur",
        "P64W+PF2 Cafe Miles by Kisan Tyres, above Kisan Tyres, Tarabai Park, Kolhapur, Maharashtra 416003, India",
    )

    assert coords is None
    assert captured_searches == [
        "P64W+PF2 Cafe Miles by Kisan Tyres, above Kisan Tyres, Tarabai Park, Kolhapur, Maharashtra 416003, India",
        "P64W+PF2, kolhapur, Maharashtra, India",
        "Maharashtra 416003, India, kolhapur",
        "Kolhapur, Maharashtra 416003, India",
        "Test Station, P64W+PF2 Cafe Miles by Kisan Tyres, above Kisan Tyres, Tarabai Park, Kolhapur, Maharashtra 416003, India",
        "kolhapur, Maharashtra, India",
    ]


def test_get_coordinates_returns_none_when_empty_address():
    res = geocoding_service.get_coordinates("")
    assert res is None


def test_get_coordinates_returns_none_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)
    res = geocoding_service.get_coordinates("Test Address")
    assert res is None


def test_get_coordinates_returns_none_on_invalid_key_401(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "dummy_key")

    class MockResponse:
        status_code = 401
        def json(self):
            return {}
        def raise_for_status(self):
            pass

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    res = geocoding_service.get_coordinates("Test Address")
    assert res is None


def test_get_coordinates_returns_none_on_rate_limit_429(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "dummy_key")

    class MockResponse:
        status_code = 429
        def json(self):
            return {}
        def raise_for_status(self):
            pass

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    res = geocoding_service.get_coordinates("Test Address")
    assert res is None


def test_get_coordinates_returns_none_on_empty_results(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "dummy_key")

    class MockResponse:
        status_code = 200
        def json(self):
            return {"results": []}
        def raise_for_status(self):
            pass

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    res = geocoding_service.get_coordinates("Test Address")
    assert res is None


def test_get_coordinates_returns_coordinates_on_success(monkeypatch):
    from decimal import Decimal
    monkeypatch.setenv("GEOAPIFY_API_KEY", "dummy_key")

    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "results": [
                    {
                        "lat": 16.712032,
                        "lon": 74.245047,
                        "formatted": "Tarabai Park, Kolhapur, Maharashtra, India"
                    }
                ]
            }
        def raise_for_status(self):
            pass

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())
    res = geocoding_service.get_coordinates("Tarabai Park, Kolhapur")
    assert res is not None
    assert res["latitude"] == Decimal("16.712032")
    assert res["longitude"] == Decimal("74.245047")
    assert res["display_name"] == "Tarabai Park, Kolhapur, Maharashtra, India"


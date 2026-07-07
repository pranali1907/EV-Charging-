from services import geocoding_service


def test_build_station_search_address_does_not_duplicate_city_state_country():
    address = "Chandran Menon Rd, Shahu Market Yard, Kolhapur, Maharashtra 416005, India"
    result = geocoding_service.build_station_search_address(
        "E-Fill Electric Charging Station",
        "kolhapur",
        address,
    )

    assert result == "E-Fill Electric Charging Station, Chandran Menon Rd, Shahu Market Yard, Kolhapur, Maharashtra 416005, India"


def test_build_address_fallback_does_not_duplicate_city_state_country():
    address = "Chandran Menon Rd, Shahu Market Yard, Kolhapur, Maharashtra 416005, India"
    result = geocoding_service.build_address_fallback("kolhapur", address)

    assert result == "Chandran Menon Rd, Shahu Market Yard, Kolhapur, Maharashtra 416005, India"

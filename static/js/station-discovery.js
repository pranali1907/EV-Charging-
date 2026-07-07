const ChargeLiveDiscovery = (() => {
    const DEFAULT_CENTER = [18.9068, 75.6742];
    const DEFAULT_ZOOM = 7;
    const suggestionCache = {};

    const isProximityKeyword = (val) => {
        if (!val) return false;
        const cleaned = val.trim().toLowerCase().replace(/\s+/g, " ");
        const keywords = [
            "near me",
            "nearby",
            "near by",
            "near by me",
            "charging station near me",
            "ev charging near me",
            "ev near me"
        ];
        return keywords.includes(cleaned);
    };

    let map;
    let stationLayer;
    let routeLayer;
    let routeMarkersLayer;
    let userMarker;
    let stations = [];
    let stationMarkers = {};
    let userLocation = null;
    let searchLocation = null; // Coordinates of single location searched
    let routeFromCoords = null;
    let routeToCoords = null;
    let activeRouteCoordinates = null;

    const elements = {};

    const init = () => {
        cacheElements();

        if (!elements.map) {
            return;
        }

        initMap();
        bindEvents();
        initAutocompleteInputs();
        loadStations();

        // Real-time Booking Integration: Refresh route recommendations every 15s if a route is active
        setInterval(() => {
            if (activeRouteCoordinates && routeFromCoords && routeToCoords) {
                resolveCoordinatesAndFindRoute();
            }
        }, 15000);
    };

    const cacheElements = () => {
        elements.map = document.getElementById("stationMap");
        elements.search = document.getElementById("stationSearch");
        elements.searchBtn = document.getElementById("searchBtn");
        elements.currentLocationBtn = document.getElementById("currentLocationBtn");
        elements.stationsList = document.getElementById("stationsList");
        elements.stationCount = document.getElementById("stationCount");
        elements.emptyState = document.getElementById("emptyState");
        elements.autocompleteDropdown = document.getElementById("autocompleteDropdown");

        // Directions panel elements
        elements.directionsToggleBtn = document.getElementById("directionsToggleBtn");
        elements.directionsPanel = document.getElementById("directionsPanel");
        elements.closeDirectionsBtn = document.getElementById("closeDirectionsBtn");
        elements.routeFrom = document.getElementById("routeFrom");
        elements.routeTo = document.getElementById("routeTo");
        elements.swapRouteBtn = document.getElementById("swapRouteBtn");
        elements.fromAutocompleteDropdown = document.getElementById("fromAutocompleteDropdown");
        elements.toAutocompleteDropdown = document.getElementById("toAutocompleteDropdown");

        // Route details card
        elements.routeSummaryCard = document.getElementById("routeSummaryCard");
        elements.routeDistance = document.getElementById("routeDistance");
        elements.routeTime = document.getElementById("routeTime");
        elements.routeStationsCount = document.getElementById("routeStationsCount");
    };

    const initMap = () => {
        map = L.map(elements.map, {
            scrollWheelZoom: true,
            zoomControl: false // Move zoom control to bottom right for clean UI
        }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

        L.control.zoom({
            position: 'bottomright'
        }).addTo(map);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap contributors",
        }).addTo(map);

        stationLayer = L.layerGroup().addTo(map);
        routeLayer = L.layerGroup().addTo(map);
        routeMarkersLayer = L.layerGroup().addTo(map);
    };

    const bindEvents = () => {
        // Toggle directions panel
        if (elements.directionsToggleBtn) {
            elements.directionsToggleBtn.addEventListener("click", () => {
                elements.directionsPanel.classList.toggle("d-none");
            });
        }
        if (elements.closeDirectionsBtn) {
            elements.closeDirectionsBtn.addEventListener("click", () => {
                elements.directionsPanel.classList.add("d-none");
            });
        }

        // Search Button trigger
        if (elements.searchBtn) {
            elements.searchBtn.addEventListener("click", () => {
                const query = elements.search.value;
                performSearch(query);
            });
        }

        // Search on Enter key
        elements.search.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                hideAutocomplete(elements.autocompleteDropdown);
                const query = elements.search.value;
                performSearch(query);
            }
        });

        // Swap route locations
        if (elements.swapRouteBtn) {
            elements.swapRouteBtn.addEventListener("click", () => {
                const tempVal = elements.routeFrom.value;
                elements.routeFrom.value = elements.routeTo.value;
                elements.routeTo.value = tempVal;

                const tempCoords = routeFromCoords;
                routeFromCoords = routeToCoords;
                routeToCoords = tempCoords;

                if (routeToCoords && elements.routeFrom.value.trim()) {
                    elements.directionsPanel.classList.remove("d-none");
                    resolveCoordinatesAndFindRoute();
                }
            });
        }

        // Near Me (Browser Geolocation)
        elements.currentLocationBtn.addEventListener("click", () => {
            searchLocation = null;
            elements.search.value = "";
            handleNearMeClick();
        });

        // Auto-select starting point text on focus/click to match Google Maps behavior
        if (elements.routeFrom) {
            elements.routeFrom.addEventListener("focus", () => {
                elements.routeFrom.select();
            });
            elements.routeFrom.addEventListener("click", () => {
                elements.routeFrom.select();
            });
        }

        // Map popup actions handler
        map.on("popupopen", (event) => {
            const popupElement = event.popup.getElement();
            const routeBtn = popupElement.querySelector(".popup-route-btn");
            if (routeBtn) {
                routeBtn.addEventListener("click", () => {
                    const lat = parseFloat(routeBtn.dataset.lat);
                    const lng = parseFloat(routeBtn.dataset.lng);
                    elements.directionsPanel.classList.remove("d-none");
                    elements.routeTo.value = "Selected Station";
                    routeToCoords = { latitude: lat, longitude: lng, label: "Selected Station" };
                    resolveCoordinatesAndFindRoute();
                });
            }
        });
    };

    const loadStations = () => {
        stations = window.CHARGELIVE_STATIONS || [];
        renderDiscovery();
        requestCurrentLocation({ auto: true });
    };

    const handleNearMeClick = () => {
        if (!navigator.geolocation) {
            alert("Geolocation not supported by this browser.");
            return;
        }

        elements.stationsList.innerHTML = `
            <div class="p-4 text-center text-muted">
                <i class="fa-solid fa-spinner fa-spin fa-2x mb-3 text-success"></i>
                <p>Acquiring GPS location...</p>
            </div>
        `;
        elements.emptyState.classList.add("d-none");

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                userLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };
                addUserMarker();

                try {
                    elements.stationsList.innerHTML = `
                        <div class="p-4 text-center text-muted">
                            <i class="fa-solid fa-spinner fa-spin fa-2x mb-3 text-success"></i>
                            <p>Searching database for nearby stations...</p>
                        </div>
                    `;
                    const filterDistEl = document.getElementById("filterDistance");
                    const radius = (filterDistEl && filterDistEl.value) ? parseFloat(filterDistEl.value) : 10.0;
                    const response = await fetch(`/api/stations/near?lat=${userLocation.latitude}&lng=${userLocation.longitude}&radius=${radius}`);
                    if (!response.ok) throw new Error("Search failed");
                    const nearbyStations = await response.json();
                    renderNearbyDiscovery(nearbyStations);
                } catch (error) {
                    console.error("Near me stations fetch failed:", error);
                    elements.stationsList.innerHTML = "";
                    elements.emptyState.classList.remove("d-none");
                    elements.emptyState.querySelector("p").textContent = "Unable to fetch nearby stations. Please try again.";
                }
            },
            (error) => {
                console.error("GPS error:", error);
                elements.stationsList.innerHTML = "";
                elements.emptyState.classList.remove("d-none");
                elements.emptyState.querySelector("h5").textContent = "Permission Required";
                elements.emptyState.querySelector("p").textContent = "Location permission is required to find nearby charging stations.";
            },
            { enableHighAccuracy: true, timeout: 7000 }
        );
    };

    const renderNearbyDiscovery = (nearbyStations) => {
        clearRoute();
        if (routeMarkersLayer) {
            routeMarkersLayer.clearLayers();
        }
        activeRouteCoordinates = null;
        elements.routeSummaryCard.classList.add("d-none");

        stationLayer.clearLayers();
        stationMarkers = {};

        nearbyStations.forEach((station) => {
            const marker = L.marker([station.latitude, station.longitude])
                .bindPopup(createPopupContent(station));
            marker.addTo(stationLayer);
            stationMarkers[station.station_id] = marker;
        });

        if (nearbyStations.length === 0) {
            elements.stationsList.innerHTML = "";
            elements.emptyState.classList.remove("d-none");
            elements.emptyState.querySelector("h5").textContent = "No Stations Found";
            const filterDistEl = document.getElementById("filterDistance");
            const radius = (filterDistEl && filterDistEl.value) ? parseInt(filterDistEl.value, 10) : 10;
            elements.emptyState.querySelector("p").textContent = `No charging stations found within ${radius} km of your current location.`;
            elements.stationCount.textContent = "0 stations found";
            return;
        }

        elements.emptyState.classList.add("d-none");

        elements.stationsList.innerHTML = nearbyStations.map(s => {
            return createStationListItem(s);
        }).join("");

        setupListCardClickEvents(nearbyStations);
        updateStationCount(nearbyStations.length);

        const fitCoords = nearbyStations.map(s => [s.latitude, s.longitude]);
        if (userLocation) {
            fitCoords.push([userLocation.latitude, userLocation.longitude]);
        }
        const bounds = L.latLngBounds(fitCoords);
        map.fitBounds(bounds, { padding: [50, 50] });
    };

    const requestCurrentLocation = (options = {}) => {
        if (!navigator.geolocation) {
            console.warn("Geolocation not supported.");
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                userLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                };
                addUserMarker();
                map.setView([userLocation.latitude, userLocation.longitude], 13);
                renderDiscovery();
                if (typeof options.onSuccess === "function") {
                    options.onSuccess();
                }
            },
            () => {
                if (!options.auto) {
                    alert("Location access was denied. Please select coordinates manually or type an address.");
                }
            },
            { enableHighAccuracy: true, timeout: 5000 }
        );
    };

    const addUserMarker = () => {
        const icon = L.divIcon({
            className: "",
            html: "<span class=\"user-location-marker\" style=\"display:block;width:16px;height:16px;border-radius:50%;background:#3b82f6;border:3px solid #ffffff;box-shadow:0 0 8px rgba(59,130,246,0.8);\"></span>",
            iconSize: [16, 16],
            iconAnchor: [8, 8],
        });

        if (userMarker) {
            map.removeLayer(userMarker);
        }

        userMarker = L.marker([userLocation.latitude, userLocation.longitude], { icon }).addTo(map);
    };

    const geocodeText = async (text) => {
        try {
            const response = await fetch(`/api/geocode/search?q=${encodeURIComponent(text)}`);
            return await response.json();
        } catch (error) {
            console.error("Geocoding failed:", error);
            return null;
        }
    };

    const resolveCoordinatesAndFindRoute = async () => {
        const fromVal = elements.routeFrom.value.trim();
        const toVal = elements.routeTo.value.trim();

        if (!fromVal || !toVal) {
            alert("Starting point and destination are required.");
            return;
        }

        let start = null;
        let dest = null;

        // 1. Resolve FROM coords
        if (fromVal === "Current Location") {
            if (!userLocation) {
                alert("Acquiring current GPS location. Please try again in a moment.");
                requestCurrentLocation();
                return;
            }
            start = { latitude: userLocation.latitude, longitude: userLocation.longitude, label: "Current Location" };
        } else if (routeFromCoords && routeFromCoords.label === fromVal) {
            start = routeFromCoords;
        } else {
            alert("Please select a starting location from the suggestion dropdown list.");
            return;
        }

        // 2. Resolve TO coords
        if (routeToCoords && routeToCoords.label === toVal) {
            dest = routeToCoords;
        } else {
            alert("Please select a destination location from the suggestion dropdown list.");
            return;
        }

        calculateRouteBetweenPoints(start, dest);
    };

    const calculateRouteBetweenPoints = async (start, dest) => {
        try {
            const origin = `${start.longitude},${start.latitude}`;
            const destination = `${dest.longitude},${dest.latitude}`;
            const response = await fetch(
                `https://router.project-osrm.org/route/v1/driving/${origin};${destination}?overview=full&geometries=geojson`
            );
            const data = await response.json();

            if (data.code !== "Ok" || !data.routes?.length) {
                alert("Routing failed. No route could be found.");
                return;
            }

            const route = data.routes[0];
            clearRoute();

            // Draw driving route line
            renderRoute(route);

            activeRouteCoordinates = route.geometry.coordinates.map(([lng, lat]) => [lat, lng]);

            // Adjust map view to fit route path
            const bounds = L.latLngBounds(activeRouteCoordinates);
            map.fitBounds(bounds, { padding: [50, 50] });

            // Draw route endpoints markers (Green/Red pins)
            addRouteStartEndMarkers(start, dest);

            // Call AI smart recommendation endpoint
            const body = {
                route_coords: activeRouteCoordinates,
                vehicle_type: document.getElementById("routeVehicleType") ? document.getElementById("routeVehicleType").value : "Car",
                battery_percent: parseFloat(document.getElementById("routeBatteryPercent") ? document.getElementById("routeBatteryPercent").value : "80"),
                remaining_range: parseFloat(document.getElementById("routeRemainingRange") ? document.getElementById("routeRemainingRange").value : "150"),
                total_duration: route.duration,
                total_distance: route.distance,
                dest_lat: dest.latitude,
                dest_lon: dest.longitude
            };

            const recommendResponse = await fetch("/api/recommend", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            const recommendations = await recommendResponse.json();

            // Render route discovery items with recommendations
            renderRouteDiscovery(recommendations, activeRouteCoordinates);

            // Populate summary card
            const distanceKm = route.distance / 1000;
            const durationMinutes = Math.round(route.duration / 60);
            elements.routeDistance.textContent = `${distanceKm.toFixed(1)} km`;
            elements.routeTime.textContent = formatDuration(durationMinutes);
            elements.routeStationsCount.textContent = recommendations.all_stations.length;
            elements.routeSummaryCard.classList.remove("d-none");

        } catch (error) {
            console.error("OSRM Route Error:", error);
            alert("Unable to calculate driving route. Please try again.");
        }
    };

    const clearRoute = () => {
        routeLayer.clearLayers();
    };

    const renderRoute = (route) => {
        const coordinates = route.geometry.coordinates.map(([lng, lat]) => [lat, lng]);
        L.polyline(coordinates, {
            color: "#3b82f6",
            weight: 6,
            opacity: 0.85,
            lineJoin: "round",
        }).addTo(routeLayer);
    };

    const addRouteStartEndMarkers = (start, dest) => {
        routeMarkersLayer.clearLayers();

        const greenIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });

        const redIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });

        L.marker([start.latitude, start.longitude], { icon: greenIcon })
            .bindPopup("<strong>Start Location</strong>")
            .addTo(routeMarkersLayer);

        L.marker([dest.latitude, dest.longitude], { icon: redIcon })
            .bindPopup("<strong>Destination Location</strong>")
            .addTo(routeMarkersLayer);
    };

    const clearRouteAndReset = () => {
        clearRoute();
        routeMarkersLayer.clearLayers();
        activeRouteCoordinates = null;
        elements.routeSummaryCard.classList.add("d-none");
        elements.routeTo.value = "";
        routeToCoords = null;

        renderDiscovery();

        if (userLocation) {
            map.setView([userLocation.latitude, userLocation.longitude], 13);
        } else {
            map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
        }
    };

    const renderDiscoveryWithStations = (stationList) => {
        let sorted = [];
        if (searchLocation) {
            sorted = stationList.map(s => ({
                ...s,
                distance_km: calculateDistanceKm(searchLocation.latitude, searchLocation.longitude, s.latitude, s.longitude)
            })).sort((a, b) => a.distance_km - b.distance_km);
        } else if (userLocation) {
            sorted = stationList.map(s => ({
                ...s,
                distance_km: calculateDistanceKm(userLocation.latitude, userLocation.longitude, s.latitude, s.longitude)
            })).sort((a, b) => a.distance_km - b.distance_km);
        } else {
            sorted = stationList.sort((a, b) => b.available_chargers - a.available_chargers);
        }

        // Drawing markers
        stationLayer.clearLayers();
        stationMarkers = {};
        sorted.forEach((station) => {
            const marker = L.marker([station.latitude, station.longitude])
                .bindPopup(createPopupContent(station));
            marker.addTo(stationLayer);
            stationMarkers[station.station_id] = marker;
        });

        // Drawing side cards list
        elements.stationsList.innerHTML = sorted.map(s => createStationListItem(s)).join("");
        elements.emptyState.classList.toggle("d-none", sorted.length > 0);

        setupListCardClickEvents(sorted);
        updateStationCount(sorted.length);
    };

    const performSearch = async (query, coords = null) => {
        const trimmedQuery = query.trim();
        if (!trimmedQuery) {
            searchLocation = null;
            clearRoute();
            renderDiscoveryWithStations(stations.filter(s => s.status === "Active"));
            return;
        }

        if (isProximityKeyword(trimmedQuery)) {
            handleNearMeClick();
            return;
        }

        clearRoute();
        if (routeMarkersLayer) {
            routeMarkersLayer.clearLayers();
        }
        activeRouteCoordinates = null;
        elements.routeSummaryCard.classList.add("d-none");

        // 1. Zoom to the searched location
        if (coords) {
            searchLocation = coords;
            map.setView([coords.latitude, coords.longitude], 13);
        } else {
            try {
                const geocodeResults = await geocodeText(trimmedQuery);
                if (geocodeResults && geocodeResults.length > 0) {
                    const firstMatch = geocodeResults[0];
                    searchLocation = {
                        latitude: firstMatch.latitude,
                        longitude: firstMatch.longitude,
                        label: firstMatch.display_name || firstMatch.name
                    };
                    map.setView([firstMatch.latitude, firstMatch.longitude], 13);
                } else {
                    searchLocation = null;
                }
            } catch (err) {
                console.error("Geocoding failed:", err);
                searchLocation = null;
            }
        }

        // 2. Call the backend search API
        try {
            const searchUrl = `/api/search?q=${encodeURIComponent(trimmedQuery)}`;
            const response = await fetch(searchUrl);
            if (!response.ok) throw new Error("Search API error");
            const freshStations = await response.json();

            // 3. Clear previous markers and cards, and display new ones
            renderDiscoveryWithStations(freshStations);

            // Zoom/fit map to matched stations if searchLocation is null and stations found
            if (freshStations.length > 0 && !searchLocation) {
                fitMapToStations(freshStations);
            }
        } catch (error) {
            console.error("Search failed:", error);
            elements.stationsList.innerHTML = "";
            elements.emptyState.classList.remove("d-none");
            updateStationCount(0);
        }
    };

    const renderDiscovery = () => {
        if (activeRouteCoordinates) {
            return;
        }

        const filtered = stations.filter((station) => {
            if (station.status !== "Active") {
                return false;
            }
            const query = elements.search.value.trim().toLowerCase();
            if (query) {
                const searchBlob = [
                    station.station_name,
                    station.city,
                    station.address,
                    station.display_name || "",
                    station.connector_types.join(" ")
                ].join(" ").toLowerCase();
                return query.split(" ").every(word => searchBlob.includes(word));
            }
            return true;
        });

        renderDiscoveryWithStations(filtered);

        if (filtered.length > 0 && elements.search.value.trim()) {
            fitMapToStations(filtered);
        }
    };

    const renderRouteDiscovery = (recommendations, activeRouteCoords) => {
        stationLayer.clearLayers();
        stationMarkers = {};

        const rec = recommendations.recommended_station;
        const busy = recommendations.nearest_busy_station;
        const alt = recommendations.alternative_station;
        const all = recommendations.all_stations;

        // Custom marker colors
        const goldIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });
        const greenIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });
        const redIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });
        const blueIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });
        const greyIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });

        // Add markers for all analyzed stations with different colors
        all.forEach((station) => {
            let icon = greyIcon;
            let popupPrefix = "";

            if (rec && station.station_id === rec.station_id) {
                icon = greenIcon; // Recommended
                popupPrefix = `<span class="badge bg-success mb-1 text-white"><i class="fa-solid fa-star me-1"></i>AI Recommended (${station.total_score}/100)</span><br>`;
            } else if (busy && station.station_id === busy.station_id) {
                icon = redIcon; // Busy
                popupPrefix = `<span class="badge bg-danger mb-1 text-white"><i class="fa-solid fa-hourglass-half me-1"></i>Nearest Busy (Wait: ${station.waiting_time}m)</span><br>`;
            } else if (alt && station.station_id === alt.station_id) {
                icon = blueIcon; // Alternative
                popupPrefix = `<span class="badge bg-primary mb-1 text-white"><i class="fa-solid fa-circle-check me-1"></i>Alternative Alt (${station.total_score}/100)</span><br>`;
            }

            const popupContent = `${popupPrefix}<strong>${station.station_name}</strong><br>
                                  <small class="text-muted">${station.address}</small><br>
                                  <span class="text-success small fw-semibold">Rs. ${station.price_per_kwh}/kWh</span><br>
                                  <span class="small text-muted">Available: ${station.available_chargers}/${station.total_chargers}</span>`;

            const marker = L.marker([station.latitude, station.longitude], { icon: icon })
                .bindPopup(popupContent);
            marker.addTo(stationLayer);
            stationMarkers[station.station_id] = marker;
        });

        // Build list elements HTML
        let html = "";

        // Render Recommendation card at the top
        if (rec) {
            const stars = "⭐".repeat(Math.min(5, Math.ceil(rec.total_score / 20)));
            const connectors = rec.connector_types
                .map((c) => `<span class="badge bg-light text-dark border me-1 small">${c}</span>`)
                .join("");

            html += `
                <div class="card border border-success border-2 shadow-lg mb-3 p-3 bg-success-subtle bg-gradient" style="border-radius: 12px;" id="station-item-${rec.station_id}">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span class="badge bg-success text-white px-2 py-1 small fw-bold"><i class="fa-solid fa-star me-1"></i>AI BEST RECOMMENDATION</span>
                        <span class="fw-bold text-success" style="font-size: 0.9rem;">${stars} ${rec.total_score}/100</span>
                    </div>
                    <h5 class="fw-bold text-dark mt-1">${rec.station_name}</h5>
                    <p class="text-muted small my-1 mb-2"><i class="fa-solid fa-map-pin me-1"></i>${rec.address}</p>
                    
                    <div class="row g-2 bg-white rounded p-2 mb-2 border shadow-sm small text-dark">
                        <div class="col-6"><strong>ETA:</strong> ${rec.eta_str} (${rec.eta_minutes} mins)</div>
                        <div class="col-6"><strong>Wait Time:</strong> ${rec.waiting_time} mins</div>
                        <div class="col-6"><strong>Distance:</strong> ${rec.station_distance_km} km</div>
                        <div class="col-6"><strong>Price:</strong> Rs. ${rec.price_per_kwh}/kWh</div>
                        <div class="col-12 border-top pt-1 mt-1 text-primary fw-semibold"><i class="fa-solid fa-lightbulb me-1"></i>${recommendations.reason}</div>
                    </div>

                    <div class="d-flex justify-content-between align-items-center">
                        <div class="connectors">
                            ${connectors}
                        </div>
                        <a href="/book/verify?station_id=${rec.station_id}&charger_id=${rec.first_charger_id}" class="btn btn-sm btn-success rounded-pill px-3 fw-bold">
                            <i class="fa-solid fa-bolt me-1"></i>Book Recommended
                        </a>
                    </div>
                </div>
            `;
        }

        // Render other analyzed stations
        all.forEach((station) => {
            if (rec && station.station_id === rec.station_id) {
                return;
            }

            const availability = getAvailabilityStatus(station);
            const statusClass = `status-${availability.className}`;

            const connectors = station.connector_types
                .map((c) => `<span class="badge bg-light text-dark border me-1 small">${c}</span>`)
                .join("");

            let badgeHtml = "";
            let cardBorder = "";
            if (busy && station.station_id === busy.station_id) {
                badgeHtml = `<span class="badge bg-danger text-white me-2">Nearest Busy (Wait: ${station.waiting_time}m)</span>`;
                cardBorder = "border-danger";
            } else if (alt && station.station_id === alt.station_id) {
                badgeHtml = `<span class="badge bg-primary text-white me-2">AI Alternative (${station.total_score}/100)</span>`;
                cardBorder = "border-primary";
            } else {
                badgeHtml = `<span class="badge bg-secondary-subtle text-secondary me-2">${station.station_distance_km} km away</span>`;
            }

            html += `
                <div class="station-list-item p-3 card border shadow-sm ${cardBorder}" id="station-item-${station.station_id}">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h6 class="text-truncate m-0 fw-bold" style="max-width: 200px;" title="${station.station_name}">${station.station_name}</h6>
                        <span class="badge ${statusClass} fs-8">${availability.label}</span>
                    </div>
                    <p class="item-address text-muted small my-1"><i class="fa-solid fa-map-pin me-1"></i>${station.address}</p>
                    <div class="item-meta my-2 d-flex align-items-center justify-content-between">
                        ${badgeHtml}
                        <span class="text-success small fw-semibold">Rs. ${station.price_per_kwh}/kWh</span>
                    </div>
                    <div class="connectors my-2">
                        ${connectors}
                    </div>
                    <div class="row g-1 pt-1 mt-1 border-top small text-muted">
                        <div class="col-6">ETA: ${station.eta_str} (${station.eta_minutes}m)</div>
                        <div class="col-6 text-end">Wait: ${station.waiting_time}m</div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center mt-2 pt-1">
                        <a href="/book/verify?station_id=${station.station_id}&charger_id=${station.first_charger_id}" class="btn btn-sm btn-outline-success rounded-pill px-3">
                            <i class="fa-solid fa-calendar-check me-1"></i>Book Now
                        </a>
                        <button class="btn btn-sm btn-outline-secondary rounded-pill px-3 card-navigate-btn" 
                                data-lat="${station.latitude}" data-lng="${station.longitude}" data-name="${station.station_name}">
                            <i class="fa-solid fa-route me-1"></i>Navigate
                        </button>
                    </div>
                </div>
            `;
        });

        elements.stationsList.innerHTML = html;
        elements.emptyState.classList.toggle("d-none", all.length > 0);

        setupListCardClickEvents(all);
        updateStationCount(all.length);
    };

    const setupListCardClickEvents = (list) => {
        elements.stationsList.querySelectorAll(".station-list-item").forEach(item => {
            item.addEventListener("click", () => {
                const stationId = parseInt(item.id.replace("station-item-", ""), 10);
                const station = list.find(s => s.station_id === stationId);
                if (station) {
                    focusOnStation(station);
                }
            });
        });

        // Setup click listeners for the Navigate button on the cards
        elements.stationsList.querySelectorAll(".card-navigate-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation(); // Prevent card fly-to action
                const lat = parseFloat(btn.dataset.lat);
                const lng = parseFloat(btn.dataset.lng);
                const name = btn.dataset.name;
                elements.directionsPanel.classList.remove("d-none");
                elements.routeTo.value = name;
                routeToCoords = { latitude: lat, longitude: lng, label: name };
                
                // Enforce current GPS starting point
                elements.routeFrom.value = "Current Location";
                routeFromCoords = null;
                
                resolveCoordinatesAndFindRoute();
            });
        });
    };

    const focusOnStation = (station) => {
        map.flyTo([station.latitude, station.longitude], 15, {
            animate: true,
            duration: 1.2
        });

        const marker = stationMarkers[station.station_id];
        if (marker) {
            marker.openPopup();
        }

        elements.stationsList.querySelectorAll(".station-list-item").forEach(c => c.classList.remove("active"));
        const card = document.getElementById(`station-item-${station.station_id}`);
        if (card) {
            card.classList.add("active");
            card.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    };

    const fitMapToStations = (matched) => {
        if (matched.length === 0) return;
        if (matched.length === 1) {
            focusOnStation(matched[0]);
            return;
        }

        const bounds = L.latLngBounds(matched.map(s => [s.latitude, s.longitude]));
        map.fitBounds(bounds, { padding: [50, 50] });
    };

    const createStationListItem = (station, activeRouteCoords = null) => {
        const availability = getAvailabilityStatus(station);
        const statusClass = `status-${availability.className}`;

        let distanceBadge = "";
        if (activeRouteCoords) {
            if (station.is_route_station) {
                const dist = station.route_distance !== undefined ? station.route_distance : getShortestDistanceToRoute(station, activeRouteCoords);
                distanceBadge = `<span class="badge bg-primary-subtle text-primary me-2"><i class="fa-solid fa-road me-1"></i>${dist.toFixed(1)} km from route</span>`;
            } else {
                const destPoint = routeToCoords || { latitude: activeRouteCoords[activeRouteCoords.length-1][0], longitude: activeRouteCoords[activeRouteCoords.length-1][1] };
                const distToDest = calculateDistanceKm(destPoint.latitude, destPoint.longitude, station.latitude, station.longitude);
                distanceBadge = `<span class="badge bg-info-subtle text-info me-2"><i class="fa-solid fa-flag me-1"></i>${distToDest.toFixed(1)} km from dest</span>`;
            }
        } else if (userLocation || searchLocation || station.distance_km !== undefined) {
            const dist = station.distance_km !== undefined ? station.distance_km : getDistanceKm(station);
            distanceBadge = `<span class="badge bg-secondary-subtle text-secondary me-2"><i class="fa-solid fa-location-dot me-1"></i>${dist.toFixed(1)} km away</span>`;
        }

        const connectors = station.connector_types
            .map((c) => `<span class="badge bg-light text-dark border me-1 small">${c}</span>`)
            .join("");

        const bookUrl = station.chargers && station.chargers.length > 0
            ? `/book/verify?station_id=${station.station_id}&charger_id=${station.chargers[0].charger_id}`
            : `/station/${station.station_id}`;

        const powerRatings = station.chargers && station.chargers.length > 0
            ? [...new Set(station.chargers.map(c => `${c.power_kw} kW`))].join(", ")
            : "N/A";

        return `
            <div class="station-list-item p-3 card border shadow-sm" id="station-item-${station.station_id}">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h6 class="text-truncate m-0 fw-bold" style="max-width: 200px;" title="${station.station_name}">${station.station_name}</h6>
                    <span class="badge ${statusClass} fs-8">${availability.label}</span>
                </div>
                <p class="item-address text-muted small my-1"><i class="fa-solid fa-map-pin me-1"></i>${station.address}</p>
                <div class="item-meta my-2 d-flex align-items-center justify-content-between">
                    ${distanceBadge}
                    <span class="text-success small fw-semibold">Rs. ${station.price_per_kwh}/kWh</span>
                </div>
                <div class="connectors my-2">
                    ${connectors}
                </div>
                <div class="charger-meta small my-2">
                    <div class="text-muted"><i class="fa-solid fa-bolt me-1 text-warning"></i><strong>Power:</strong> ${powerRatings}</div>
                    <div class="text-muted mt-1">
                        <i class="fa-solid fa-plug me-1 text-primary"></i><strong>Status:</strong> 
                        <span class="text-success">Avail: ${station.available_chargers}</span> &middot; 
                        <span class="text-danger">Busy: ${station.busy_chargers}</span> &middot; 
                        <span class="text-secondary">Offline: ${station.offline_chargers}</span>
                    </div>
                </div>
                <div class="d-flex gap-2 mt-3 pt-2 border-top">
                    <button class="btn btn-sm btn-outline-primary rounded-pill flex-grow-1 card-navigate-btn" 
                        data-lat="${station.latitude}" 
                        data-lng="${station.longitude}" 
                        data-name="${station.station_name}">
                        <i class="fa-solid fa-diamond-turn-right me-1"></i>Navigate
                    </button>
                    <a class="btn btn-sm btn-success rounded-pill flex-grow-1 text-center" 
                        href="${bookUrl}" 
                        onclick="event.stopPropagation();">
                        <i class="fa-solid fa-calendar-check me-1"></i>Book Slot
                    </a>
                </div>
            </div>
        `;
    };

    const createPopupContent = (station, activeRouteCoords = null) => {
        let routeDistanceText = "";
        if (activeRouteCoords) {
            if (station.is_route_station) {
                const dist = getShortestDistanceToRoute(station, activeRouteCoords);
                routeDistanceText = `<p class="mb-1"><strong>Route Distance:</strong> ${dist.toFixed(1)} km</p>`;
            } else {
                const destPoint = routeToCoords || { latitude: activeRouteCoords[activeRouteCoords.length-1][0], longitude: activeRouteCoords[activeRouteCoords.length-1][1] };
                const distToDest = calculateDistanceKm(destPoint.latitude, destPoint.longitude, station.latitude, station.longitude);
                routeDistanceText = `<p class="mb-1"><strong>Destination Distance:</strong> ${distToDest.toFixed(1)} km</p>`;
            }
        } else if (userLocation || searchLocation || station.distance_km !== undefined) {
            const dist = station.distance_km !== undefined ? station.distance_km : getDistanceKm(station);
            routeDistanceText = `<p class="mb-1"><strong>Distance:</strong> ${dist.toFixed(1)} km</p>`;
        }

        const bookUrl = station.chargers && station.chargers.length > 0
            ? `/book/verify?station_id=${station.station_id}&charger_id=${station.chargers[0].charger_id}`
            : `/station/${station.station_id}`;

        return `
            <div class="station-popup">
                <h3>${station.station_name}</h3>
                <p class="mb-1"><strong>Address:</strong> ${station.address}</p>
                ${routeDistanceText}
                <p class="mb-1"><strong>Price:</strong> Rs. ${station.price_per_kwh}/kWh</p>
                <p class="mb-1"><strong>Availability:</strong> Available: ${station.available_chargers} | Busy: ${station.busy_chargers} | Offline: ${station.offline_chargers}</p>
                <p class="mb-1"><strong>Connectors:</strong> ${station.connector_types.join(", ")}</p>
                <div class="d-flex gap-2 mt-3">
                    <button class="btn btn-xs btn-primary rounded-pill popup-route-btn" data-lat="${station.latitude}" data-lng="${station.longitude}">
                        <i class="fa-solid fa-diamond-turn-right me-1"></i>Navigate
                    </button>
                    <a class="btn btn-xs btn-success rounded-pill" href="${bookUrl}">
                        <i class="fa-solid fa-calendar-check me-1"></i>Book Slot
                    </a>
                </div>
            </div>
        `;
    };

    const getAvailabilityStatus = (station) => {
        if (station.status !== "Active") {
            return { className: "offline", label: "Inactive" };
        }
        if (station.available_chargers > 0) {
            return { className: "available", label: `${station.available_chargers} available` };
        }
        if (station.busy_chargers > 0) {
            return { className: "busy", label: "Busy" };
        }
        return { className: "offline", label: "Offline" };
    };

    const getDistanceKm = (station) => {
        const origin = searchLocation || userLocation;
        if (!origin) {
            return Number.POSITIVE_INFINITY;
        }
        return calculateDistanceKm(
            origin.latitude,
            origin.longitude,
            station.latitude,
            station.longitude
        );
    };

    const calculateDistanceKm = (lat1, lon1, lat2, lon2) => {
        const earthRadiusKm = 6371;
        const dLat = toRadians(lat2 - lat1);
        const dLon = toRadians(lon2 - lon1);
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
            + Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2))
            * Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return earthRadiusKm * c;
    };

    const isStationInDestinationCity = (station, destinationText) => {
        if (!destinationText) return false;
        const destLower = destinationText.toLowerCase();
        const cityLower = (station.city || "").toLowerCase();
        return destLower.includes(cityLower) || cityLower.includes(destLower);
    };

    const toRadians = (degrees) => degrees * (Math.PI / 180);

    const getShortestDistanceToRoute = (station, routeCoords) => {
        if (!routeCoords || routeCoords.length < 2) {
            return 0;
        }

        let minDistanceKm = Number.POSITIVE_INFINITY;
        const p = { lat: station.latitude, lng: station.longitude };

        for (let i = 0; i < routeCoords.length - 1; i++) {
            const v = { lat: routeCoords[i][0], lng: routeCoords[i][1] };
            const w = { lat: routeCoords[i + 1][0], lng: routeCoords[i + 1][1] };

            const l2 = sqr(v.lat - w.lat) + sqr(v.lng - w.lng);
            let t = 0;
            if (l2 !== 0) {
                t = ((p.lat - v.lat) * (w.lat - v.lat) + (p.lng - v.lng) * (w.lng - v.lng)) / l2;
                t = Math.max(0, Math.min(1, t));
            }

            const projection = {
                latitude: v.lat + t * (w.lat - v.lat),
                longitude: v.lng + t * (w.lng - v.lng)
            };

            const distance = calculateDistanceKm(
                p.lat, p.lng,
                projection.latitude, projection.longitude
            );

            if (distance < minDistanceKm) {
                minDistanceKm = distance;
            }
        }

        return minDistanceKm;
    };

    const sqr = (x) => x * x;

    const formatDuration = (minutes) => {
        if (minutes < 60) {
            return `${minutes} min`;
        }
        const hours = Math.floor(minutes / 60);
        const rem = minutes % 60;
        return rem > 0 ? `${hours} hr ${rem} min` : `${hours} hr`;
    };

    const updateStationCount = (count) => {
        const label = count === 1 ? "station" : "stations";
        elements.stationCount.textContent = `${count} ${label} found`;
    };

    const dedupeAutocompleteItems = (items) => {
        const seenNames = new Set();
        const seenCoords = new Set();
        const filtered = [];

        const normalizeText = (text) =>
            (text || "").trim().toLowerCase().replace(/\s+/g, " ");

        items.forEach((item) => {
            const rawName = item.station_id
                ? `${item.station_name} | ${item.city || ""} | ${item.state || ""} | ${item.country || ""}`
                : `${item.display_name || item.name || ""} | ${item.city || ""} | ${item.state || ""} | ${item.country || ""}`;
            const nameKey = normalizeText(rawName);
            const latitude = Number(item.latitude);
            const longitude = Number(item.longitude);
            const coordKey = Number.isFinite(latitude) && Number.isFinite(longitude)
                ? `${latitude.toFixed(6)},${longitude.toFixed(6)}`
                : null;

            if (coordKey && seenCoords.has(coordKey)) {
                return;
            }
            if (nameKey && seenNames.has(nameKey)) {
                return;
            }

            if (coordKey) {
                seenCoords.add(coordKey);
            }
            if (nameKey) {
                seenNames.add(nameKey);
            }

            filtered.push(item);
        });

        return filtered;
    };

    // Autocomplete Setup
    const initAutocompleteInputs = () => {
        setupAutocomplete(
            elements.search,
            elements.autocompleteDropdown,
            (item) => {
                if (item.station_id) {
                    elements.search.value = item.station_name;
                    hideAutocomplete(elements.autocompleteDropdown);
                    performSearch(item.station_name).then(() => {
                        focusOnStation(item);
                    });
                } else {
                    elements.search.value = item.display_name;
                    hideAutocomplete(elements.autocompleteDropdown);
                    const coords = { latitude: item.latitude, longitude: item.longitude, label: item.display_name };
                    performSearch(item.display_name, coords);
                }
            },
            true // include stations
        );

        setupAutocomplete(
            elements.routeFrom,
            elements.fromAutocompleteDropdown,
            (item) => {
                elements.routeFrom.value = item.display_name;
                routeFromCoords = { latitude: item.latitude, longitude: item.longitude, label: item.display_name };
                hideAutocomplete(elements.fromAutocompleteDropdown);
                if (routeToCoords) {
                    elements.directionsPanel.classList.remove("d-none");
                    resolveCoordinatesAndFindRoute();
                }
            },
            false // locations only
        );

        setupAutocomplete(
            elements.routeTo,
            elements.toAutocompleteDropdown,
            (item) => {
                elements.routeTo.value = item.display_name;
                routeToCoords = { latitude: item.latitude, longitude: item.longitude, label: item.display_name };
                hideAutocomplete(elements.toAutocompleteDropdown);
                elements.directionsPanel.classList.remove("d-none");

                if (elements.routeFrom.value.trim() === "Current Location" && !userLocation) {
                    requestCurrentLocation({ auto: true, onSuccess: resolveCoordinatesAndFindRoute });
                } else {
                    resolveCoordinatesAndFindRoute();
                }
            },
            false // locations only
        );
    };

    const setupAutocomplete = (input, dropdown, onSelect, includeStations = false) => {
        let timer = null;
        let activeSuggestionIndex = -1;
        let suggestionsList = [];

        const showSuggestions = (items) => {
            suggestionsList = items;
            dropdown.innerHTML = "";
            activeSuggestionIndex = -1;

            if (items.length === 0) {
                dropdown.innerHTML = `
                    <div class="p-2 text-center text-muted small">
                        No matching locations found.
                    </div>
                `;
                dropdown.classList.remove("d-none");
                return;
            }

            items.forEach((item, idx) => {
                const div = document.createElement("div");
                div.className = "autocomplete-item p-2 border-bottom";
                div.style.cursor = "pointer";

                let icon = "📍";
                let subtitle = "Location";
                let titleText = item.display_name;

                if (item.station_id) {
                    icon = "🔌";
                    subtitle = `EV Station • ${item.city}`;
                    titleText = item.station_name;
                } else {
                    const parts = [];
                    if (item.name) parts.push(item.name);
                    if (item.city && item.city !== item.name) parts.push(item.city);
                    if (item.state) parts.push(item.state);
                    if (item.country) parts.push(item.country);
                    titleText = item.name || item.display_name.split(",")[0];
                    subtitle = parts.slice(1).join(", ") || item.display_name;
                }

                div.innerHTML = `
                    <div class="d-flex align-items-center gap-2">
                        <span class="fs-5">${icon}</span>
                        <div class="text-truncate">
                            <div class="fw-semibold text-truncate small" style="max-width: 320px;">${titleText}</div>
                            <div class="text-muted small text-truncate" style="max-width: 320px;">${subtitle}</div>
                        </div>
                    </div>
                `;

                div.addEventListener("click", () => {
                    onSelect(item);
                });

                dropdown.appendChild(div);
            });

            dropdown.classList.remove("d-none");
        };

        const updateHighlight = () => {
            const items = dropdown.querySelectorAll(".autocomplete-item");
            items.forEach((item, idx) => {
                if (idx === activeSuggestionIndex) {
                    item.classList.add("bg-success-subtle", "text-success");
                    item.scrollIntoView({ behavior: "smooth", block: "nearest" });
                } else {
                    item.classList.remove("bg-success-subtle", "text-success");
                }
            });
        };

        input.addEventListener("input", () => {
            clearTimeout(timer);

            if (input === elements.search) {
                searchLocation = null;
            } else if (input === elements.routeFrom) {
                routeFromCoords = null;
            } else if (input === elements.routeTo) {
                routeToCoords = null;
            }

            const query = input.value.trim();

            if (input === elements.search && isProximityKeyword(query)) {
                dropdown.classList.add("d-none");
                dropdown.innerHTML = "";
                return;
            }

            if (query.length < 2) {
                dropdown.classList.add("d-none");
                dropdown.innerHTML = "";
                return;
            }

            dropdown.innerHTML = `
                <div class="p-3 text-center text-muted small">
                    <i class="fa-solid fa-spinner fa-spin me-2 text-success"></i>Searching...
                </div>
            `;
            dropdown.classList.remove("d-none");

            timer = setTimeout(async () => {
                const cacheKey = `${query}_${includeStations}`;
                if (suggestionCache[cacheKey]) {
                    showSuggestions(suggestionCache[cacheKey]);
                    return;
                }

                try {
                    let items = [];
                    const placeRes = await fetch(`/api/geocode/search?q=${encodeURIComponent(query)}`);
                    if (!placeRes.ok) throw new Error("API failed");
                    const places = await placeRes.json();
                    items = items.concat(places);

                    if (includeStations) {
                        const stationRes = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                        if (stationRes.ok) {
                            const stationsList = await stationRes.json();
                            items = stationsList.concat(items);
                        }
                    }

                    items = dedupeAutocompleteItems(items);
                    suggestionCache[cacheKey] = items;
                    showSuggestions(items);
                } catch (error) {
                    console.error("Autocomplete fetch error:", error);
                    dropdown.innerHTML = `
                        <div class="p-2 text-center text-danger small">
                            <i class="fa-solid fa-circle-exclamation me-1"></i> Unable to retrieve suggestions.
                        </div>
                    `;
                }
            }, 300);
        });

        input.addEventListener("keydown", (e) => {
            if (dropdown.classList.contains("d-none")) return;

            const itemsCount = suggestionsList.length;

            if (e.key === "ArrowDown") {
                e.preventDefault();
                activeSuggestionIndex = (activeSuggestionIndex + 1) % itemsCount;
                updateHighlight();
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                activeSuggestionIndex = (activeSuggestionIndex - 1 + itemsCount) % itemsCount;
                updateHighlight();
            } else if (e.key === "Enter") {
                e.preventDefault();
                if (activeSuggestionIndex >= 0 && activeSuggestionIndex < itemsCount) {
                    onSelect(suggestionsList[activeSuggestionIndex]);
                } else if (itemsCount > 0) {
                    onSelect(suggestionsList[0]);
                }
            } else if (e.key === "Escape") {
                dropdown.classList.add("d-none");
            }
        });

        input.addEventListener("focus", () => {
            const query = input.value.trim();
            if (input === elements.routeFrom && !query) {
                dropdown.innerHTML = "";
                const div = document.createElement("div");
                div.className = "autocomplete-item p-2 border-bottom fw-semibold text-primary";
                div.style.cursor = "pointer";
                div.innerHTML = `
                    <div class="d-flex align-items-center gap-2">
                        <span class="fs-5">🎯</span>
                        <div class="small">Use Current Location</div>
                    </div>
                `;
                div.addEventListener("click", () => {
                    input.value = "Current Location";
                    routeFromCoords = null; // resets to GPS userLocation
                    dropdown.classList.add("d-none");
                });
                dropdown.appendChild(div);
                dropdown.classList.remove("d-none");
            } else if (query && dropdown.innerHTML) {
                dropdown.classList.remove("d-none");
            }
        });

        document.addEventListener("click", (event) => {
            if (!input.contains(event.target) && !dropdown.contains(event.target)) {
                dropdown.classList.add("d-none");
            }
        });
    };

    const hideAutocomplete = (dropdown) => {
        if (dropdown) {
            dropdown.classList.add("d-none");
            dropdown.innerHTML = "";
        }
    };

    return {
        init,
    };
})();

document.addEventListener("DOMContentLoaded", ChargeLiveDiscovery.init);

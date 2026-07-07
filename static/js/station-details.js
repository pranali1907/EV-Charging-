const ChargeLiveStationDetails = (() => {
    let map;
    let userMarker;
    let routeLayer;
    let routeSteps = [];
    let navigationWatchId = null;
    let routeDestination = null;
    let routeData = null;

    const init = () => {
        const detailMap = document.getElementById("stationDetailMap");

        if (!detailMap) {
            return;
        }

        initDetailMap(detailMap);
        initNavigationControls(detailMap);
        initDistance();
        initShareButton();
    };

    const initDetailMap = (detailMap) => {
        const latitude = Number(detailMap.dataset.latitude);
        const longitude = Number(detailMap.dataset.longitude);
        const stationName = detailMap.dataset.stationName;
        const city = detailMap.dataset.city;

        map = L.map(detailMap, {
            scrollWheelZoom: false,
        }).setView([latitude, longitude], 14);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap contributors",
        }).addTo(map);

        L.marker([latitude, longitude])
            .addTo(map)
            .bindPopup(`<strong>${stationName}</strong><br>${city}`);

        routeLayer = L.layerGroup().addTo(map);
    };

    const initNavigationControls = (detailMap) => {
        const startButton = document.getElementById("startNavigationBtn");
        const stopButton = document.getElementById("stopNavigationBtn");

        if (!startButton || !stopButton || !navigator.geolocation) {
            return;
        }

        routeDestination = {
            latitude: Number(detailMap.dataset.latitude),
            longitude: Number(detailMap.dataset.longitude),
        };

        startButton.addEventListener("click", () => {
            startNavigation();
            startButton.classList.add("d-none");
            stopButton.classList.remove("d-none");
        });

        stopButton.addEventListener("click", () => {
            stopNavigation();
            stopButton.classList.add("d-none");
            startButton.classList.remove("d-none");
        });
    };

    const startNavigation = () => {
        if (!navigator.geolocation) {
            setNavigationStatus("Browser geolocation is not supported.", "danger");
            return;
        }

        setNavigationStatus("Starting navigation…", "info");
        requestCurrentPosition(true);

        navigationWatchId = navigator.geolocation.watchPosition(
            (position) => {
                const userLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                };

                updateUserMarker(userLocation);
                updateRoute(userLocation);
            },
            (error) => {
                setNavigationStatus("Unable to retrieve location. Please allow location access.", "danger");
            },
            {
                enableHighAccuracy: true,
                maximumAge: 0,
                timeout: 15000,
            }
        );
    };

    const stopNavigation = () => {
        if (navigationWatchId !== null) {
            navigator.geolocation.clearWatch(navigationWatchId);
            navigationWatchId = null;
        }

        routeLayer.clearLayers();
        routeSteps = [];
        routeData = null;
        setNavigationStatus("Navigation stopped.", "warning");
        setNavigationMetrics("--", "--");
        setNextTurn("Navigation stopped.");
        renderNavigationSteps([]);
    };

    const requestCurrentPosition = (isNavigationStart = false) => {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const userLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                };

                updateUserMarker(userLocation);

                if (isNavigationStart) {
                    requestRoute(userLocation, routeDestination);
                }
            },
            () => {
                setNavigationStatus("Unable to detect current location.", "danger");
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 0,
            }
        );
    };

    const updateUserMarker = (userLocation) => {
        const icon = L.divIcon({
            className: "",
            html: "<span class=\"user-location-marker\"></span>",
            iconSize: [18, 18],
            iconAnchor: [9, 9],
        });

        if (userMarker) {
            userMarker.setLatLng([userLocation.latitude, userLocation.longitude]);
        } else {
            userMarker = L.marker([userLocation.latitude, userLocation.longitude], { icon })
                .addTo(map)
                .bindPopup("Your location");
        }

        map.setView([userLocation.latitude, userLocation.longitude], 14);
    };

    const requestRoute = async (origin, destination) => {
        setNavigationStatus("Calculating route…", "info");

        try {
            const response = await fetch(
                `https://router.project-osrm.org/route/v1/driving/${origin.longitude},${origin.latitude};${destination.longitude},${destination.latitude}?overview=full&geometries=geojson&steps=true&alternatives=false`
            );

            const data = await response.json();

            if (data.code !== "Ok" || !data.routes?.length) {
                throw new Error("No route available.");
            }

            routeData = data.routes[0];
            renderRoute(routeData);
            renderRouteDetails(routeData);
            setNavigationStatus("Navigation active.", "success");
        } catch (error) {
            console.error(error);
            setNavigationStatus("Unable to calculate route.", "danger");
            renderRouteDetails(null);
        }
    };

    const updateRoute = (userLocation) => {
        if (!routeData) {
            return;
        }

        requestRoute(userLocation, routeDestination);
    };

    const renderRoute = (route) => {
        routeLayer.clearLayers();

        const coordinates = route.geometry.coordinates.map(([lng, lat]) => [lat, lng]);
        L.polyline(coordinates, {
            color: "#2f8bfd",
            weight: 5,
            opacity: 0.8,
        }).addTo(routeLayer);
    };

    const renderRouteDetails = (route) => {
        const etaElement = document.getElementById("navigationEta");
        const distanceElement = document.getElementById("navigationDistance");
        const nextTurnElement = document.getElementById("nextTurn");
        const stepsElement = document.getElementById("navigationSteps");

        if (!route) {
            setNavigationMetrics("--", "--");
            setNextTurn("Unable to calculate route.");
            renderNavigationSteps([]);
            return;
        }

        const distanceKm = route.distance / 1000;
        const durationMin = Math.round(route.duration / 60);
        const nextStep = route.legs[0]?.steps?.[0];
        routeSteps = route.legs[0]?.steps || [];

        setNavigationMetrics(`${distanceKm.toFixed(1)} km`, `${durationMin} min`);
        setNextTurn(nextStep ? formatStepInstruction(nextStep) : "No turn instructions available.");
        renderNavigationSteps(routeSteps);
    };

    const setNavigationMetrics = (distance, eta) => {
        const etaElement = document.getElementById("navigationEta");
        const distanceElement = document.getElementById("navigationDistance");

        if (etaElement) {
            etaElement.textContent = eta;
        }

        if (distanceElement) {
            distanceElement.textContent = distance;
        }
    };

    const setNavigationStatus = (message, type = "info") => {
        const statusElement = document.getElementById("navigationStatus");

        if (statusElement) {
            statusElement.textContent = message;
            statusElement.className = "navigation-status text-" + type;
        }
    };

    const setNextTurn = (text) => {
        const nextTurnElement = document.getElementById("nextTurn");

        if (nextTurnElement) {
            nextTurnElement.textContent = text;
        }
    };

    const renderNavigationSteps = (steps) => {
        const stepsElement = document.getElementById("navigationSteps");

        if (!stepsElement) {
            return;
        }

        stepsElement.innerHTML = steps.map((step, index) => `<li>${formatStepInstruction(step)}</li>`).join("");
    };

    const formatStepInstruction = (step) => {
        const distanceMeters = Math.round(step.distance);
        const instruction = step.maneuver.instruction || step.maneuver.type;
        return `${instruction} — ${distanceMeters} m`;
    };

    const initDistance = () => {
        const distanceElement = document.getElementById("detailDistance");

        if (!distanceElement || !navigator.geolocation) {
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const stationLatitude = Number(distanceElement.dataset.latitude);
                const stationLongitude = Number(distanceElement.dataset.longitude);
                const distance = calculateDistanceKm(
                    position.coords.latitude,
                    position.coords.longitude,
                    stationLatitude,
                    stationLongitude
                );

                distanceElement.textContent = `${distance.toFixed(1)} km`;
            },
            () => {
                distanceElement.textContent = "Allow location";
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000,
            }
        );
    };

    const initShareButton = () => {
        const shareButton = document.getElementById("shareLocationBtn");

        if (!shareButton) {
            return;
        }

        shareButton.addEventListener("click", async () => {
            const latitude = shareButton.dataset.latitude;
            const longitude = shareButton.dataset.longitude;
            const stationName = shareButton.dataset.stationName;
            const locationUrl = `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=16/${latitude}/${longitude}`;
            const shareData = {
                title: stationName,
                text: `ChargeLive station location: ${stationName}`,
                url: locationUrl,
            };

            try {
                if (navigator.share) {
                    await navigator.share(shareData);
                    return;
                }

                if (navigator.clipboard) {
                    await navigator.clipboard.writeText(locationUrl);
                    setShareButtonMessage(shareButton, "Location Copied", "fa-check");
                    return;
                }

                window.prompt("Copy station location", locationUrl);
            } catch (error) {
                setShareButtonMessage(shareButton, "Share Location", "fa-share-nodes");
            }
        });
    };

    const setShareButtonMessage = (button, label, icon) => {
        button.innerHTML = `<i class="fa-solid ${icon} me-2"></i>${label}`;

        window.setTimeout(() => {
            button.innerHTML = "<i class=\"fa-solid fa-share-nodes me-2\"></i>Share Location";
        }, 2200);
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

    const toRadians = (degrees) => degrees * (Math.PI / 180);

    return {
        init,
    };
})();

document.addEventListener("DOMContentLoaded", ChargeLiveStationDetails.init);

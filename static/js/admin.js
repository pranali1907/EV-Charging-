const ChargeLiveAdmin = (() => {
    const init = () => {
        initPasswordToggle();
        initSidebarToggle();
        initStationHoursToggle();
        initStationGeocoding();
        initConnectorDefaults();
    };

    const initStationHoursToggle = () => {
        const open24Hours = document.getElementById("isOpen24Hours");
        const openingTime = document.getElementById("openingTime");
        const closingTime = document.getElementById("closingTime");

        if (!open24Hours || !openingTime || !closingTime) {
            return;
        }

        const syncHours = () => {
            const isOpen24Hours = open24Hours.checked;
            openingTime.disabled = isOpen24Hours;
            closingTime.disabled = isOpen24Hours;
            openingTime.required = !isOpen24Hours;
            closingTime.required = !isOpen24Hours;
        };

        open24Hours.addEventListener("change", syncHours);
        syncHours();
    };

    const initPasswordToggle = () => {
        const toggle = document.getElementById("togglePassword");
        const password = document.getElementById("password");

        if (!toggle || !password) {
            return;
        }

        toggle.addEventListener("click", () => {
            const isPassword = password.type === "password";
            password.type = isPassword ? "text" : "password";
            toggle.setAttribute(
                "aria-label",
                isPassword ? "Hide password" : "Show password"
            );
            toggle.innerHTML = isPassword
                ? "<i class=\"bi bi-eye-slash\"></i>"
                : "<i class=\"bi bi-eye\"></i>";
        });
    };

    const initStationGeocoding = () => {
        const button = document.getElementById("getLocationBtn");
        const stationName = document.getElementById("stationName");
        const city = document.getElementById("city");
        const address = document.getElementById("address");
        const latitude = document.getElementById("latitude");
        const longitude = document.getElementById("longitude");
        const displayName = document.getElementById("displayName");
        const latitudePreview = document.getElementById("latitudePreview");
        const longitudePreview = document.getElementById("longitudePreview");
        const preview = document.getElementById("locationPreview");
        const displayText = document.getElementById("locationDisplayText");
        const mapElement = document.getElementById("stationLocationMap");
        const feedback = document.getElementById("locationFeedback");

        if (!button || !stationName || !city || !address || !mapElement) {
            return;
        }

        let map = null;
        let marker = null;

        const setLocationFeedback = (message, type = "muted") => {
            if (!feedback) {
                return;
            }

            const classMap = {
                danger: "text-danger",
                info: "text-muted",
                success: "text-success",
                warning: "text-warning",
            };

            feedback.className = `small mt-2 ${classMap[type] || classMap.info}`;
            feedback.textContent = message || "";
        };

        const showMap = (lat, lng, label) => {
            preview.classList.remove("d-none");

            if (!map) {
                map = L.map(mapElement).setView([lat, lng], 16);
                L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                    attribution: "&copy; OpenStreetMap contributors",
                }).addTo(map);
            }

            map.setView([lat, lng], 16);

            if (!marker) {
                marker = L.marker([lat, lng]).addTo(map);
            } else {
                marker.setLatLng([lat, lng]);
            }

            marker.bindPopup(label || "Verified station location").openPopup();
            setTimeout(() => map.invalidateSize(), 50);
        };

        const clearVerifiedLocation = () => {
            latitude.value = "";
            longitude.value = "";
            displayName.value = "";
            setLocationFeedback("");

            if (latitudePreview) {
                latitudePreview.value = "";
                latitudePreview.setAttribute("readonly", "readonly");
            }

            if (longitudePreview) {
                longitudePreview.value = "";
                longitudePreview.setAttribute("readonly", "readonly");
            }

            if (displayText) {
                displayText.textContent = "";
            }
        };

        const syncManualCoordinates = () => {
            latitude.value = (latitudePreview.value || "").trim();
            longitude.value = (longitudePreview.value || "").trim();
            displayName.value = `${address.value}, ${city.value}`.trim();
        };

        if (latitudePreview && longitudePreview) {
            latitudePreview.addEventListener("input", syncManualCoordinates);
            longitudePreview.addEventListener("input", syncManualCoordinates);
        }

        [stationName, city, address].forEach((field) => {
            field.addEventListener("input", clearVerifiedLocation);
        });

        if (latitude.value && longitude.value) {
            showMap(Number(latitude.value), Number(longitude.value), displayName.value);
        }

        button.addEventListener("click", async () => {
            const payload = {
                station_name: stationName.value,
                city: city.value,
                address: address.value,
                station_id: button.dataset.stationId || null,
            };

            button.disabled = true;
            button.innerHTML = "<span class=\"spinner-border spinner-border-sm me-1\"></span>Getting Location";
            setLocationFeedback("Checking address and station location...", "info");

            try {
                const response = await fetch(button.dataset.geocodeUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(payload),
                });
                const data = await response.json();

                if (!response.ok || !data.success) {
                    throw new Error(data.message || "Unable to locate this address.");
                }

                latitude.value = data.latitude;
                longitude.value = data.longitude;
                displayName.value = data.display_name || "";

                if (latitudePreview) {
                    latitudePreview.value = data.latitude;
                    latitudePreview.setAttribute("readonly", "readonly");
                }

                if (longitudePreview) {
                    longitudePreview.value = data.longitude;
                    longitudePreview.setAttribute("readonly", "readonly");
                }

                if (displayText) {
                    displayText.textContent = data.display_name || data.search_address || "";
                }

                setLocationFeedback(data.message || "Location verified successfully.", "success");
                showMap(Number(data.latitude), Number(data.longitude), data.display_name);
            } catch (error) {
                clearVerifiedLocation();
                if (latitudePreview && longitudePreview && preview) {
                    preview.classList.remove("d-none");
                    latitudePreview.removeAttribute("readonly");
                    longitudePreview.removeAttribute("readonly");
                    setLocationFeedback(`${error.message} Please enter the latitude and longitude coordinates manually below.`, "danger");
                } else {
                    setLocationFeedback(error.message, "danger");
                }
            } finally {
                button.disabled = false;
                button.innerHTML = "<i class=\"bi bi-crosshair me-1\"></i>Get Location";
            }
        });
    };

    const initConnectorDefaults = () => {
        const connector = document.getElementById("connectorType");
        const power = document.getElementById("powerKw");
        const vehicle = document.getElementById("vehicleType");

        if (!connector || !power || !vehicle) {
            return;
        }

        connector.addEventListener("change", () => {
            const selected = connector.options[connector.selectedIndex];

            if (!selected) {
                return;
            }

            if (!power.value && selected.dataset.power) {
                power.value = selected.dataset.power;
            }

            vehicle.value = selected.dataset.vehicle || "";
        });

        connector.dispatchEvent(new Event("change"));
    };

    const initSidebarToggle = () => {
        const toggle = document.getElementById("sidebarToggle");
        const sidebar = document.getElementById("adminSidebar");

        if (!toggle || !sidebar) {
            return;
        }

        toggle.addEventListener("click", () => {
            sidebar.classList.toggle("is-open");
        });
    };

    return {
        init,
    };
})();

document.addEventListener("DOMContentLoaded", ChargeLiveAdmin.init);

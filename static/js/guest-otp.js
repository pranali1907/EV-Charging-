(function () {
    const mobileInputs = document.querySelectorAll('input[name="mobile_number"]');
    const otpInput = document.querySelector('input[name="otp"]');
    const forms = document.querySelectorAll(".otp-form");

    mobileInputs.forEach((input) => {
        input.addEventListener("input", () => {
            input.value = input.value.replace(/\D/g, "").slice(0, 10);
        });
    });

    if (otpInput) {
        otpInput.addEventListener("input", () => {
            otpInput.value = otpInput.value.replace(/\D/g, "").slice(0, 6);
        });
    }

    forms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }

            form.classList.add("was-validated");
        });
    });
})();

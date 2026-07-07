document.addEventListener("DOMContentLoaded", () => {
    const navbar = document.querySelector(".chargelive-navbar");

    const updateNavbarShadow = () => {
        if (window.scrollY > 8) {
            navbar.classList.add("navbar-scrolled");
            return;
        }

        navbar.classList.remove("navbar-scrolled");
    };

    updateNavbarShadow();
    window.addEventListener("scroll", updateNavbarShadow);
});

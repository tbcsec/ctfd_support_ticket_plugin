(function () {
  "use strict";

  if (window.location.pathname.startsWith("/admin")) return;

  document.addEventListener("DOMContentLoaded", function () {

    // Try multiple selectors to account for differences across CTFd versions
    const selectors = [
      "ul.navbar-nav",
      "nav ul.nav",
      ".navbar-nav",
      "#navbarSupportedContent ul",
      "nav .nav",
    ];

    let navList = null;
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el) {
        console.debug("[Support Plugin] Navbar found with selector:", selector, el);
        navList = el;
        break;
      }
    }

    if (!navList) {
      console.warn("[Support Plugin] Could not find navbar element. Tried:", selectors);
      console.debug("[Support Plugin] Full nav HTML:", document.querySelector("nav")?.innerHTML);
      return;
    }

    const li = document.createElement("li");
    li.className = "nav-item";
    li.innerHTML = '<a class="nav-link" href="/support">Support</a>';
    navList.appendChild(li);
    console.debug("[Support Plugin] Support link injected successfully.");
  });
})();
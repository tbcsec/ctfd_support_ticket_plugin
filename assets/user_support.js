// assets/user_support.js
document.addEventListener("DOMContentLoaded", function () {
  // CTFd's default theme uses a <ul class="navbar-nav"> for nav items.
  // We skip admin pages — admins access support via the Plugins menu.
  if (window.location.pathname.startsWith("/admin")) return;

  const navList = document.querySelector("ul.navbar-nav");
  if (!navList) return;

  const li = document.createElement("li");
  li.className = "nav-item";
  li.innerHTML = '<a class="nav-link" href="/support">Support Tickets</a>';
  navList.appendChild(li);
});
/**
 * admin_support.js
 * ─────────────────
 * Runs only on admin pages.  Every 30 seconds it polls /api/support/open_count
 * and:
 *   1. Updates a badge on the "Support Tickets" link in the admin Plugins menu.
 *   2. Shows a Bootstrap toast notification if the open count has increased
 *      since the last poll (i.e. a new ticket was submitted).
 *
 * The last known count is persisted in localStorage so that a page refresh
 * does not re-trigger the toast for tickets that were already known about.
 */

(function () {
  "use strict";

  // Only activate on admin pages.
  if (!window.location.pathname.startsWith("/admin")) return;

  const POLL_INTERVAL_MS = 30_000;
  const STORAGE_KEY      = "support_last_open_count";
  const API_URL          = "/api/support/open_count";

  // ── Badge ──────────────────────────────────────────────────────────────────

  /**
   * Find the "Support Tickets" anchor in the Plugins dropdown and attach (or
   * update) a Bootstrap badge showing the current open ticket count.
   */
  function updateBadge(count) {
    // The Plugins dropdown is rendered by CTFd's admin base template.
    // We locate our link by matching its href.
    const link = document.querySelector('a[href="/admin/support"]');
    if (!link) return;

    let badge = link.querySelector(".support-open-badge");
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "badge badge-danger ml-1 support-open-badge";
      link.appendChild(badge);
    }

    if (count > 0) {
      badge.textContent = count;
      badge.style.display = "inline-block";
    } else {
      badge.style.display = "none";
    }
  }

  // ── Toast ──────────────────────────────────────────────────────────────────

  /**
   * Inject a Bootstrap 4 toast container into the page (once) and return it.
   */
  function getOrCreateToastContainer() {
    let container = document.getElementById("support-toast-container");
    if (container) return container;

    container = document.createElement("div");
    container.id = "support-toast-container";
    Object.assign(container.style, {
      position:  "fixed",
      top:       "70px",
      right:     "20px",
      zIndex:    "9999",
      minWidth:  "300px",
    });
    document.body.appendChild(container);
    return container;
  }

  /**
   * Show a dismissable Bootstrap toast alerting admins to a new ticket.
   *
   * @param {number} newCount   Current open ticket count.
   * @param {number} delta      How many new tickets appeared since last poll.
   */
  function showNewTicketToast(newCount, delta) {
    const container = getOrCreateToastContainer();

    const noun = delta === 1 ? "ticket" : "tickets";
    const html = `
      <div class="toast show" role="alert" aria-live="assertive"
           aria-atomic="true" data-autohide="false"
           style="min-width:300px; margin-bottom:8px;">
        <div class="toast-header bg-danger text-white">
          <strong class="mr-auto">
            <i class="fas fa-ticket-alt mr-1"></i> Support Tickets
          </strong>
          <button type="button" class="ml-2 mb-1 close text-white"
                  data-dismiss="toast" aria-label="Close">
            <span aria-hidden="true">&times;</span>
          </button>
        </div>
        <div class="toast-body">
          <strong>${delta} new support ${noun}</strong> submitted.
          There ${newCount === 1 ? "is" : "are"} now
          <strong>${newCount}</strong> open ${newCount === 1 ? "ticket" : "tickets"}.
          <a href="/admin/support" class="d-block mt-1">View tickets &rarr;</a>
        </div>
      </div>`;

    const wrapper = document.createElement("div");
    wrapper.innerHTML = html.trim();
    const toast = wrapper.firstChild;
    container.appendChild(toast);

    // Wire up the close button (Bootstrap 4 may or may not be initialised).
    const closeBtn = toast.querySelector('[data-dismiss="toast"]');
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        toast.remove();
      });
    }

    // Also auto-dismiss after 10 seconds.
    setTimeout(function () {
      if (toast.parentNode) toast.remove();
    }, 10_000);
  }

  // ── Poll loop ──────────────────────────────────────────────────────────────

  let lastKnownCount = parseInt(
    localStorage.getItem(STORAGE_KEY) ?? "-1",
    10
  );

  function poll() {
    fetch(API_URL, { credentials: "same-origin" })
      .then(function (res) {
        if (!res.ok) return;
        return res.json();
      })
      .then(function (data) {
        if (!data || typeof data.open_count !== "number") return;

        const count = data.open_count;
        updateBadge(count);

        if (lastKnownCount >= 0 && count > lastKnownCount) {
          // New tickets have appeared since the last poll.
          showNewTicketToast(count, count - lastKnownCount);
        }

        lastKnownCount = count;
        localStorage.setItem(STORAGE_KEY, String(count));
      })
      .catch(function () {
        // Silently ignore network / auth errors (e.g. logged-out admin).
      });
  }

  // Run immediately once the DOM is ready, then on a timer.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", poll);
  } else {
    poll();
  }

  setInterval(poll, POLL_INTERVAL_MS);
})();

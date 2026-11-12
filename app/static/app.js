(function () {
  "use strict";

  var DETAILS_KEY = "glasshouse.details.v1";
  var SHOW_ALL_KEY = "glasshouse.showAll";
  var HANDLED = new Set(["submitted", "waiting", "removed", "refused"]);

  function loadDetails() {
    try {
      return JSON.parse(localStorage.getItem(DETAILS_KEY) || "{}");
    } catch (err) {
      return {};
    }
  }

  var details = loadDetails();

  function saveDetails() {
    try {
      localStorage.setItem(DETAILS_KEY, JSON.stringify(details));
    } catch (err) {
      /* storage disabled — copy buttons still work from the inputs */
    }
  }

  document.querySelectorAll("[data-detail]").forEach(function (input) {
    var key = input.getAttribute("data-detail");
    if (details[key]) input.value = details[key];
    input.addEventListener("input", function () {
      details[key] = input.value;
      saveDetails();
    });
  });

  function detailValue(kind) {
    if (kind === "address") {
      return [details.address, details.city, details.postcode].filter(Boolean).join(", ");
    }
    var input = document.querySelector('[data-detail="' + kind + '"]');
    return (input && input.value) || details[kind] || "";
  }

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var value = detailValue(button.getAttribute("data-copy"));
      var original = button.textContent;
      if (!value) {
        button.textContent = "Fill it in first ↑";
        setTimeout(function () {
          button.textContent = original;
        }, 1500);
        return;
      }
      function done() {
        button.textContent = "Copied ✓";
        setTimeout(function () {
          button.textContent = original;
        }, 1400);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(done, fallback);
      } else {
        fallback();
      }
      function fallback() {
        var area = document.createElement("textarea");
        area.value = value;
        document.body.appendChild(area);
        area.select();
        try {
          document.execCommand("copy");
        } catch (err) {
          /* ignore */
        }
        area.remove();
        done();
      }
    });
  });

  var cards = Array.prototype.slice.call(document.querySelectorAll("[data-broker-card]"));
  var showAllToggle = document.getElementById("show-all");

  function applyVisibility() {
    if (!cards.length) return;
    var showAll = showAllToggle ? showAllToggle.checked : false;
    if (showAll) {
      cards.forEach(function (card) {
        card.hidden = false;
      });
    } else {
      var next = null;
      for (var i = 0; i < cards.length; i += 1) {
        if (!HANDLED.has(cards[i].getAttribute("data-state"))) {
          next = cards[i];
          break;
        }
      }
      cards.forEach(function (card) {
        card.hidden = next ? card !== next : false;
      });
    }
    document.querySelectorAll("[data-region-block]").forEach(function (block) {
      block.hidden = !block.querySelector("[data-broker-card]:not([hidden])");
    });
  }

  if (showAllToggle) {
    showAllToggle.checked = localStorage.getItem(SHOW_ALL_KEY) === "1";
    showAllToggle.addEventListener("change", function () {
      try {
        localStorage.setItem(SHOW_ALL_KEY, showAllToggle.checked ? "1" : "0");
      } catch (err) {
        /* ignore */
      }
      applyVisibility();
    });
  }

  function updateProgress() {
    if (!cards.length) return;
    var done = cards.filter(function (card) {
      return HANDLED.has(card.getAttribute("data-state"));
    }).length;
    var bar = document.getElementById("broker-bar");
    var label = document.getElementById("broker-count");
    if (bar) bar.style.width = Math.round((100 * done) / cards.length) + "%";
    if (label) label.textContent = done + " of " + cards.length + " brokers done";
  }

  applyVisibility();
  updateProgress();

  document.querySelectorAll("form[data-broker-form]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var submitter = event.submitter;
      var data;
      try {
        data = submitter ? new FormData(form, submitter) : new FormData(form);
      } catch (err) {
        data = new FormData(form);
      }
      if (submitter && submitter.getAttribute("data-state")) {
        data.set("state", submitter.getAttribute("data-state"));
      }
      var card = form.closest("[data-broker-card]");
      fetch(form.action, {
        method: "POST",
        body: data,
        headers: { "X-Requested-With": "fetch" }
      })
        .then(function (response) {
          if (!response.ok) throw new Error("bad status");
          if (card) card.setAttribute("data-state", data.get("state") || "submitted");
          applyVisibility();
          updateProgress();
          window.scrollTo({ top: 0, behavior: "smooth" });
        })
        .catch(function () {
          form.submit();
        });
    });
  });

  var exportButton = document.getElementById("export-plan");
  if (exportButton) {
    exportButton.addEventListener("click", function () {
      var node = document.getElementById("plan-data");
      if (!node) return;
      var stamp = new Date().toISOString().slice(0, 10);
      var blob = new Blob([node.textContent], { type: "application/json" });
      var url = URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = url;
      link.download = "glasshouse-plan-" + stamp + ".json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(function () {
        URL.revokeObjectURL(url);
      }, 1000);
    });
  }
})();

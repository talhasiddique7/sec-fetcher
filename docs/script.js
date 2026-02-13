(function () {
  "use strict";

  var root = document.documentElement;
  var toggle = document.getElementById("themeToggle");
  var savedTheme = localStorage.getItem("secfetch_docs_theme");
  if (savedTheme === "light" || savedTheme === "dark") {
    root.setAttribute("data-theme", savedTheme);
  }

  function syncToggleLabel() {
    var theme = root.getAttribute("data-theme") || "dark";
    if (!toggle) return;
    toggle.textContent = theme === "dark" ? "🌙 Dark" : "☀️ Light";
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      var now = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", now);
      localStorage.setItem("secfetch_docs_theme", now);
      syncToggleLabel();
    });
  }
  syncToggleLabel();

  var navLinks = Array.prototype.slice.call(document.querySelectorAll(".sidebar a[href^='#']"));
  var sections = Array.prototype.slice.call(document.querySelectorAll(".section[id]"));

  function updateActive() {
    var top = window.scrollY || document.documentElement.scrollTop;
    var chosen = sections[0] ? sections[0].id : "";
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].offsetTop - 120 <= top) {
        chosen = sections[i].id;
      }
    }
    navLinks.forEach(function (a) {
      var id = (a.getAttribute("href") || "").slice(1);
      a.classList.toggle("is-active", id === chosen);
    });
  }
  window.addEventListener("scroll", function () {
    requestAnimationFrame(updateActive);
  });
  window.addEventListener("load", updateActive);

  var blocks = document.querySelectorAll("pre.code");
  blocks.forEach(function (block) {
    var code = block.querySelector("code");
    if (!code) return;
    var btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.textContent = "Copy";
    block.appendChild(btn);

    btn.addEventListener("click", function () {
      var text = code.textContent || "";
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = "Copied";
        setTimeout(function () {
          btn.textContent = "Copy";
        }, 1200);
      }).catch(function () {
        btn.textContent = "Failed";
        setTimeout(function () {
          btn.textContent = "Copy";
        }, 1200);
      });
    });
  });
})();

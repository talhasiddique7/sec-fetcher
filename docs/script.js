(function () {
  "use strict";

  // Mark nav link as active when section is in view
  var sections = document.querySelectorAll(".content .section[id]");
  var navLinks = document.querySelectorAll(".nav-list a[href^='#']");

  function getActiveId() {
    var top = window.scrollY || document.documentElement.scrollTop;
    var headerOffset = 100;
    for (var i = sections.length - 1; i >= 0; i--) {
      var section = sections[i];
      var id = section.getAttribute("id");
      if (!id) continue;
      var el = document.getElementById(id);
      if (el && el.offsetTop - headerOffset <= top) return id;
    }
    return sections[0] ? sections[0].getAttribute("id") : null;
  }

  function updateNav() {
    var activeId = getActiveId();
    navLinks.forEach(function (link) {
      var href = link.getAttribute("href");
      var id = href && href.startsWith("#") ? href.slice(1) : null;
      link.classList.toggle("is-active", id === activeId);
    });
  }

  window.addEventListener("scroll", function () {
    requestAnimationFrame(updateNav);
  });
  window.addEventListener("load", updateNav);

  // Copy button for code blocks
  document.querySelectorAll(".code-block").forEach(function (block) {
    var code = block.querySelector("code");
    if (!code) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.textContent = "Copy";
    btn.setAttribute("aria-label", "Copy code");
    block.style.paddingTop = "2.25rem";
    block.appendChild(btn);
    btn.addEventListener("click", function () {
      var text = code.textContent;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () {
            btn.textContent = "Copied!";
            btn.classList.add("copied");
            setTimeout(function () {
              btn.textContent = "Copy";
              btn.classList.remove("copied");
            }, 2000);
          },
          function () {
            fallbackCopy(text, btn);
          }
        );
      } else {
        fallbackCopy(text, btn);
      }
    });
  });

  function fallbackCopy(text, btn) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      btn.textContent = "Copied!";
      btn.classList.add("copied");
      setTimeout(function () {
        btn.textContent = "Copy";
        btn.classList.remove("copied");
      }, 2000);
    } catch (e) {}
    document.body.removeChild(ta);
  }
})();

// Navbar hamburger toggle.
document.addEventListener("DOMContentLoaded", function () {
  const toggler = document.querySelector('[data-toggle="collapse"]');
  const target = toggler && document.querySelector(toggler.getAttribute("data-target"));
  if (!target) {
    return;
  }
  const navbar = document.querySelector(".navbar");
  let animating = false;

  // Run `done` when the height transition ends, with a timeout fallback for when
  // it never fires (e.g. prefers-reduced-motion disables the transition).
  function afterHeightTransition(done) {
    let finished = false;
    function finish(event) {
      if (finished || (event && (event.target !== target || event.propertyName !== "height"))) {
        return;
      }
      finished = true;
      target.removeEventListener("transitionend", finish);
      done();
    }
    target.addEventListener("transitionend", finish);
    setTimeout(finish, 400);
  }

  function open() {
    animating = true;
    if (navbar) {
      navbar.classList.add("top-nav-expanded");
    }
    target.classList.remove("collapse");
    target.classList.add("collapsing");
    target.style.height = "0px";
    target.getBoundingClientRect(); // force reflow so the transition runs
    target.style.height = target.scrollHeight + "px";
    afterHeightTransition(function () {
      target.classList.remove("collapsing");
      target.classList.add("collapse", "show");
      target.style.height = "";
      animating = false;
    });
  }

  function close() {
    animating = true;
    target.style.height = target.scrollHeight + "px";
    target.getBoundingClientRect(); // force reflow
    target.classList.add("collapsing");
    target.classList.remove("collapse", "show");
    target.style.height = "0px";
    afterHeightTransition(function () {
      target.classList.remove("collapsing");
      target.classList.add("collapse");
      target.style.height = "";
      if (navbar) {
        navbar.classList.remove("top-nav-expanded");
      }
      animating = false;
    });
  }

  toggler.addEventListener("click", function () {
    if (animating) {
      return;
    }
    const isOpen = target.classList.contains("show");
    toggler.setAttribute("aria-expanded", isOpen ? "false" : "true");
    if (isOpen) {
      close();
    } else {
      open();
    }
  });
});

// Askbase landing: starfield, live demo of question -> query -> table with a pause button,
// scroll reveals, bars and counters. Under prefers-reduced-motion everything is shown in its final state.
(() => {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- navigation border on scroll ----------
  const nav = document.querySelector(".nav");
  const onScroll = () => nav && nav.classList.toggle("scrolled", window.scrollY > 8);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // ---------- platform: Windows visitors see the Windows status first ----------
  if (/Windows/i.test(navigator.userAgent)) document.documentElement.classList.add("win");

  // ---------- particle starburst, from the space above the demo ----------
  const canvas = document.getElementById("stars");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    let w = 0, h = 0, stars = [], visible = true, running = false;
    const build = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.round((w * h) / 9000);
      stars = Array.from({ length: n }, () => ({
        a: Math.random() * Math.PI * 2, r: Math.random() * Math.max(w, h) * 0.8, s: 0.02 + Math.random() * 0.12, z: Math.random(),
      }));
    };
    const draw = () => {
      const R = Math.max(w, h), cx = w * 0.5, cy = h * 0.34;   // behind the wordmark
      ctx.clearRect(0, 0, w, h);
      for (const p of stars) {
        const x = cx + Math.cos(p.a) * p.r, y = cy + Math.sin(p.a) * p.r * 0.62;
        const fade = Math.min(1, p.r / 220) * (1 - p.r / (R * 0.95));
        ctx.globalAlpha = Math.max(0, fade) * (0.25 + p.z * 0.55);
        ctx.fillStyle = "#fff";
        ctx.fillRect(x, y, 1 + p.z, 1 + p.z);
      }
    };
    const tick = () => {
      if (!visible) { running = false; return; }
      const R = Math.max(w, h);
      for (const p of stars) { p.r += p.s * (0.4 + p.z); if (p.r > R * 0.9) p.r = Math.random() * 40; }
      draw();
      requestAnimationFrame(tick);
    };
    const start = () => { if (!running && !reduce) { running = true; requestAnimationFrame(tick); } };
    build();
    draw(); // one static frame, also under reduced motion
    let lastW = w, timer;
    window.addEventListener("resize", () => {
      clearTimeout(timer);
      timer = setTimeout(() => { if (canvas.clientWidth !== lastW) { lastW = canvas.clientWidth; build(); draw(); } }, 150);
    });
    new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) start(); }).observe(canvas);
  }


  // ---------- depth: the card follows the pointer in perspective ----------
  // Small angles on purpose. The brand asks for restraint and scale, so this
  // reads as the object having thickness, not as the page showing off.
  document.querySelectorAll(".tilt").forEach((box) => {
    if (reduce) return;
    const MAX = 5.5;                      // degrees
    let raf = null, rx = 0, ry = 0;
    const apply = () => {
      raf = null;
      box.style.setProperty("--rx", rx.toFixed(2) + "deg");
      box.style.setProperty("--ry", ry.toFixed(2) + "deg");
    };
    const move = (e) => {
      const r = box.getBoundingClientRect();
      // -1..1 from the centre of the card
      const px = (e.clientX - r.left) / r.width * 2 - 1;
      const py = (e.clientY - r.top) / r.height * 2 - 1;
      ry = Math.max(-1, Math.min(1, px)) * MAX;
      rx = Math.max(-1, Math.min(1, -py)) * MAX * 0.7;
      if (!raf) raf = requestAnimationFrame(apply);
    };
    const rest = () => { rx = 0; ry = 0; box.classList.remove("live"); if (!raf) raf = requestAnimationFrame(apply); };
    // Pointer only: a touch drag must scroll the page, not tilt a card.
    box.addEventListener("pointermove", (e) => { if (e.pointerType !== "mouse") return; box.classList.add("live"); move(e); });
    box.addEventListener("pointerleave", rest);
    box.addEventListener("blur", rest, true);
  });

  // ---------- live demo: three steps, one frame at a time ----------
  // The product is question -> query -> answer, so the demo is literally those
  // three, shown in the same space. Visitors can click a step; the rail doubles
  // as the explanation of what the application does.
  const ask = document.querySelector(".ask");
  if (ask) {
    const panes = [...ask.querySelectorAll(".panes .pane")];
    const tabs = [...ask.querySelectorAll(".rail button")];
    const qEl = ask.querySelector(".q .text");
    const question = qEl ? qEl.dataset.q || "" : "";
    const pause = ask.querySelector(".pause");
    const HOLD = [1500, 2300, 5200];        // how long each step stays, ms
    let paused = reduce, hover = false, step = 0, seq = 0, timer = null, typer = null;

    const stop = () => { clearTimeout(timer); clearInterval(typer); };
    const paint = (k) => {
      step = k;
      panes.forEach((p, i) => (i === k ? p.setAttribute("data-on", "") : p.removeAttribute("data-on")));
      tabs.forEach((b, i) => (i === k ? b.setAttribute("aria-current", "step") : b.removeAttribute("aria-current")));
      ask.classList.toggle("showsql", k === 1);
      ask.classList.toggle("showrows", k === 2);
      ask.classList.toggle("showsaid", k === 2);
    };

    // Step 0 types the question; the other two just appear.
    const enter = (k, mine) => {
      const alive = () => mine === seq && !paused && !hover;
      paint(k);
      if (k !== 0) { if (qEl) qEl.textContent = question; ask.classList.remove("typing"); return; }
      ask.classList.add("typing");
      if (qEl) qEl.textContent = "";
      let i = 0;
      typer = setInterval(() => {
        if (!alive()) { clearInterval(typer); if (qEl) qEl.textContent = question; ask.classList.remove("typing"); return; }
        if (qEl) qEl.textContent = question.slice(0, ++i);
        if (i >= question.length) { clearInterval(typer); ask.classList.remove("typing"); }
      }, 32);
    };

    const run = (from) => {
      const mine = ++seq;
      stop();
      const go = (k) => {
        if (mine !== seq || paused || hover) return;
        enter(k, mine);
        // step 0 needs the typing time on top of its hold
        const extra = k === 0 ? question.length * 32 : 0;
        timer = setTimeout(() => go((k + 1) % panes.length), HOLD[k] + extra);
      };
      go(from);
    };

    const settle = () => { stop(); seq++; if (qEl) qEl.textContent = question; ask.classList.remove("typing"); };
    const label = () => {
      if (!pause) return;
      pause.setAttribute("aria-pressed", String(paused));
      pause.textContent = paused ? pause.dataset.play : pause.dataset.stop;
    };

    tabs.forEach((b, i) => b.addEventListener("click", () => {
      settle(); paint(i);
      if (!paused && !hover) run(i);
    }));
    if (pause) pause.addEventListener("click", () => {
      paused = !paused; label();
      if (paused) settle(); else run(step);
    });
    // Reading beats animating: stop while the pointer or focus is on the card.
    ask.addEventListener("mouseenter", () => { hover = true; settle(); });
    ask.addEventListener("mouseleave", () => { hover = false; if (!paused) run(step); });
    ask.addEventListener("focusin", () => { hover = true; settle(); });
    ask.addEventListener("focusout", () => { hover = false; if (!paused) run(step); });

    if (reduce) { paint(2); settle(); label(); }
    else {
      label();
      new IntersectionObserver(([e]) => {
        if (e.isIntersecting) { if (!paused && !hover) run(step); } else { settle(); }
      }, { threshold: 0.25 }).observe(ask);
    }
  }

  // ---------- reveals, bars, counters ----------
  const finish = (el) => {
    el.classList.add("in");
    el.querySelectorAll(".fill[data-w]").forEach((f) => (f.style.transform = `scaleX(${Math.max(0.004, f.dataset.w / 100)})`));
    if (!reduce) el.querySelectorAll("[data-count]").forEach(count);
  };
  document.querySelectorAll(".types li").forEach((li, k) => li.style.setProperty("--i", k));
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { finish(e.target); io.unobserve(e.target); }
  }, { threshold: 0.18 });
  document.querySelectorAll(".reveal, .bars, .giant").forEach((el) => (reduce ? finish(el) : io.observe(el)));

  // counts up to the number already printed in the page (only for figures where bigger is better)
  function count(el) {
    const final = el.textContent;
    const target = parseFloat(el.dataset.count);
    if (!isFinite(target)) return;
    const t0 = performance.now(), dur = 1400;
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur), v = Math.round(target * (1 - Math.pow(1 - k, 3)));
      el.firstChild.textContent = String(v);
      if (k < 1) requestAnimationFrame(step); else el.innerHTML = el.dataset.final;
    };
    el.dataset.final = el.innerHTML;
    el.innerHTML = `<span>0</span>${el.innerHTML.replace(/^[\d\s ,]+/, "")}`;
    requestAnimationFrame(step);
  }
})();

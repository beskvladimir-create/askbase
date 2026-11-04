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

/* Cookie consent. The banner shows only when nothing has been chosen, and the
   choice reaches the tag rather than only the browser: a banner that writes
   to localStorage and leaves the tag alone is theatre, and on the next page
   load the consent default would read the stored value and contradict what
   the visitor saw happen. So both are done, in that order. */
(function () {
  var KEY = "askbase-cookie-consent";
  var box = document.getElementById("consent");
  if (!box) return;
  var stored = null;
  try { stored = localStorage.getItem(KEY); } catch (e) { /* private window */ }
  if (stored === "accepted" || stored === "denied") return;
  box.hidden = false;
  box.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-consent]");
    if (!btn) return;
    var choice = btn.dataset.consent;
    try { localStorage.setItem(KEY, choice); } catch (err) { /* nothing to do */ }
    if (typeof gtag === "function") {
      gtag("consent", "update", {
        analytics_storage: choice === "accepted" ? "granted" : "denied"
      });
    }
    box.hidden = true;
  });
})();

/* Таблица рейтинга. Числа приходят из data-атрибутов строк, которые сборщик
   подставил из results/, а здесь из них рисуются ячейки. Все пять метрик
   меряются на каждом языке отдельно, поэтому переключатель языка меняет
   таблицу целиком, а не один столбец. Строки в разметке пустые: если
   JavaScript выключен, таблицы просто нет, и это лучше, чем половина
   таблицы, по которой непонятно, какой язык показан. */
(function () {
  var table = document.getElementById("lb");
  if (!table) return;
  var rows = Array.prototype.slice.call(table.tBodies[0].rows);
  if (!rows.length) return;
  /* Страница задаёт, какой язык открывается первым: ru на русской версии,
     en на английской. Посетитель может переключить в любую сторону. */
  var lang = table.dataset.lang === "en" ? "en" : "ru";
  var sortKey = "ex";
  var dir = -1;
  var ru = document.documentElement.lang === "ru";

  function val(row, key) {
    return parseFloat(row.dataset[key + (lang === "ru" ? "Ru" : "En")]);
  }

  function cell(text) { return "<td>" + text + "</td>"; }

  /* Русское склонение по числу. Наивное «1 модель, меньше пяти модели,
     иначе моделей» даёт «0 модели» и «11 модели», а ноль здесь обычное
     значение: когда лидер отрывается, в его полосе никого нет. */
  function plural(n) {
    var ten = n % 10;
    var hundred = n % 100;
    if (ten === 1 && hundred !== 11) return "модель";
    if (ten >= 2 && ten <= 4 && (hundred < 12 || hundred > 14)) return "модели";
    return "моделей";
  }

  function render() {
    /* Номер в первом столбце это всегда место по точности, чтобы сортировка
       по задержке не перенумеровывала рейтинг. */
    var byScore = rows.slice().sort(function (a, b) { return val(b, "ex") - val(a, "ex"); });
    var leader = byScore[0];
    var lo = lang === "ru" ? "loRu" : "loEn";
    var hi = lang === "ru" ? "hiRu" : "hiEn";
    byScore.forEach(function (r, i) {
      r._place = i + 1;
      /* Целые интервалы, пересекающиеся с интервалом лидера, при таком n
         друг от друга не отличимы. */
      r._tie = i > 0 &&
        parseFloat(r.dataset[lo]) <= parseFloat(leader.dataset[hi]) &&
        parseFloat(r.dataset[hi]) >= parseFloat(leader.dataset[lo]);
    });

    var order = rows.slice().sort(function (a, b) {
      var d = (val(a, sortKey) - val(b, sortKey)) * dir;
      return d !== 0 ? d : val(b, "ex") - val(a, "ex");
    });

    var note = document.getElementById("tiecount");
    if (note) {
      var n = rows.filter(function (r) { return r._tie; }).length;
      note.textContent = ru
        ? n + " " + plural(n) + " из " + rows.length
        : n + " of " + rows.length + " models";
    }

    var body = table.tBodies[0];
    order.forEach(function (r) {
      var d = r.dataset;
      r.className = (r._place === 1 ? "top " : "") + (r._tie ? "tie" : "");
      r.innerHTML =
        '<td class="pos">' + r._place + "</td>" +
        '<td class="name">' + d.model + "<small>" + d.sub + "</small></td>" +
        '<td class="main"><span class="score">' + val(r, "ex").toFixed(1) + "%</span>" +
        '<span class="track"><span class="fill" style="transform:scaleX(' +
          (val(r, "ex") / 100).toFixed(3) + ')"></span></span>' +
        '<span class="ci">' + parseFloat(d[lo]).toFixed(1) + " – " +
          parseFloat(d[hi]).toFixed(1) + "</span></td>" +
        cell(val(r, "ns").toFixed(1) + "%") +
        cell(val(r, "agr").toFixed(1) + "%") +
        cell(val(r, "p95").toFixed(2) + (ru ? " с" : " s")) +
        cell(val(r, "fa").toFixed(1) + "%");
      body.appendChild(r);
    });
  }

  table.tHead.addEventListener("click", function (e) {
    var th = e.target.closest("th.sortable");
    if (!th) return;
    var key = th.dataset.key;
    if (key === sortKey) { dir = -dir; } else { sortKey = key; dir = key === "p95" ? 1 : -1; }
    Array.prototype.forEach.call(table.tHead.rows[0].cells, function (c) {
      c.removeAttribute("aria-sort");
    });
    th.setAttribute("aria-sort", dir === -1 ? "descending" : "ascending");
    render();
  });

  document.querySelectorAll(".seg button[data-lang]").forEach(function (b) {
    b.addEventListener("click", function () {
      lang = b.dataset.lang;
      document.querySelectorAll(".seg button[data-lang]").forEach(function (x) {
        x.setAttribute("aria-pressed", String(x === b));
      });
      render();
    });
  });

  render();
})();

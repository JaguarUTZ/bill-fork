/* Forkashi skin. Sounds are oscillators only: original cues, no audio files. */
(function forkashiSkin() {
  const COPY = window.FORKASHI_COPY;
  if (!COPY) return;

  const SOUND_KEY = "forkashi-sound";
  const LANG_KEY = "forkashi-lang";
  const HOWTO_KEY = "forkashi-howto";
  const SPLASH_KEY = "forkashi-splash";
  const SOUND_ON = "Sound: ON";
  const SOUND_OFF = "Sound: OFF";
  const BPM = 96;
  const BEAT = 60 / BPM;
  /* Original 4-bar loop, one note per beat, A dorian shape. Not a borrowed theme. */
  const LEAD = [
    440, 523.25, 587.33, 659.25, 587.33, 523.25, 440, 392, 659.25, 783.99,
    880, 783.99, 659.25, 587.33, 523.25, 440,
  ];
  const BASS = [110, 87.31, 130.81, 98];

  let lang = "en";
  let enabled = false;
  let gesture = false;
  let ctx = null;
  let cueGain = null;
  let loopGain = null;
  let loopOn = false;
  let loopTimer = 0;
  let nextAt = 0;
  let lastKind = "";
  let lastBill = null;
  let opener = null;
  let topic = "";

  function readStore(area, key) {
    try {
      return area.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function writeStore(area, key, value) {
    try {
      area.setItem(key, value);
    } catch (error) {
      /* Private mode can block storage. The desk still works. */
    }
  }

  function pack() {
    return COPY[lang] || COPY.en;
  }

  function pixelIcon(rects) {
    const body = rects
      .map(function (rect) {
        return (
          '<rect x="' +
          rect[0] +
          '" y="' +
          rect[1] +
          '" width="' +
          rect[2] +
          '" height="' +
          rect[3] +
          '" fill="currentColor"/>'
        );
      })
      .join("");
    return (
      '<svg viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true">' +
      body +
      "</svg>"
    );
  }

  const ICONS = {
    loading: pixelIcon([
      [2, 7, 2, 2],
      [7, 7, 2, 2],
      [12, 7, 2, 2],
    ]),
    none: pixelIcon([
      [2, 2, 12, 2],
      [2, 12, 12, 2],
      [2, 2, 2, 12],
      [12, 2, 2, 12],
    ]),
    sent: pixelIcon([
      [1, 7, 8, 2],
      [8, 5, 2, 2],
      [10, 6, 2, 2],
      [12, 7, 2, 2],
      [10, 8, 2, 2],
      [8, 9, 2, 2],
    ]),
    accepted: pixelIcon([
      [0, 3, 9, 2],
      [0, 12, 9, 2],
      [0, 3, 2, 11],
      [7, 3, 2, 11],
      [2, 6, 5, 2],
      [2, 9, 3, 2],
      [10, 1, 5, 2],
      [10, 1, 2, 8],
      [13, 1, 2, 8],
      [10, 7, 5, 2],
      [12, 3, 2, 3],
    ]),
    settled: pixelIcon([
      [2, 8, 2, 2],
      [4, 10, 2, 2],
      [6, 12, 2, 2],
      [8, 10, 2, 2],
      [10, 8, 2, 2],
      [12, 6, 2, 2],
      [14, 4, 2, 2],
    ]),
    attention: pixelIcon([
      [2, 2, 12, 2],
      [2, 12, 12, 2],
      [2, 2, 2, 12],
      [12, 2, 2, 12],
      [7, 4, 2, 5],
      [7, 10, 2, 2],
    ]),
  };

  function audio() {
    if (!enabled || !gesture) return null;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return null;
    if (!ctx) {
      ctx = new AudioCtx();
      const master = ctx.createGain();
      master.gain.value = 0.85;
      master.connect(ctx.destination);
      cueGain = ctx.createGain();
      cueGain.connect(master);
      loopGain = ctx.createGain();
      loopGain.gain.value = 0;
      loopGain.connect(master);
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  function tone(type, freq, when, dur, peak, dest, slideTo) {
    const ac = audio();
    if (!ac || !dest) return;
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, when);
    if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, when + dur);
    gain.gain.setValueAtTime(0.0001, when);
    gain.gain.exponentialRampToValueAtTime(peak, when + Math.min(0.015, dur / 3));
    gain.gain.exponentialRampToValueAtTime(0.0001, when + dur);
    osc.connect(gain);
    gain.connect(dest);
    osc.start(when);
    osc.stop(when + dur + 0.03);
  }

  function blip() {
    const ac = audio();
    if (!ac) return;
    tone("square", 640, ac.currentTime, 0.05, 0.045, cueGain, 880);
  }

  function coin() {
    const ac = audio();
    if (!ac) return;
    const start = ac.currentTime;
    [587.33, 698.46, 880, 1174.66].forEach(function (freq, index) {
      tone("triangle", freq, start + index * 0.07, 0.16, 0.06, cueGain);
    });
  }

  function buzz() {
    const ac = audio();
    if (!ac) return;
    const start = ac.currentTime;
    tone("square", 146, start, 0.18, 0.04, cueGain, 78);
    tone("square", 97, start, 0.18, 0.03, cueGain, 60);
  }

  function pump() {
    if (!loopOn) return;
    const ac = audio();
    if (!ac || !loopGain) return;
    const loopLen = LEAD.length * BEAT;
    if (nextAt < ac.currentTime + 0.05) nextAt = ac.currentTime + 0.06;
    const start = nextAt;
    LEAD.forEach(function (freq, index) {
      tone("square", freq, start + index * BEAT, BEAT * 0.4, 0.028, loopGain);
    });
    BASS.forEach(function (freq, bar) {
      tone("triangle", freq, start + bar * 4 * BEAT, BEAT * 1.4, 0.04, loopGain);
      tone("triangle", freq * 2, start + (bar * 4 + 2) * BEAT, BEAT * 0.8, 0.02, loopGain);
    });
    nextAt = start + loopLen;
    const wait = Math.max(200, (nextAt - ac.currentTime - 0.3) * 1000);
    loopTimer = window.setTimeout(pump, wait);
  }

  function startLoop() {
    if (loopOn) return;
    const ac = audio();
    if (!ac || !loopGain) return;
    const splash = document.getElementById("splash");
    if (!splash || !splash.open) return;
    loopGain.gain.cancelScheduledValues(ac.currentTime);
    loopGain.gain.setValueAtTime(1, ac.currentTime);
    loopOn = true;
    nextAt = 0;
    pump();
  }

  function stopLoop() {
    loopOn = false;
    if (loopTimer) {
      window.clearTimeout(loopTimer);
      loopTimer = 0;
    }
    if (ctx && loopGain) {
      loopGain.gain.cancelScheduledValues(ctx.currentTime);
      loopGain.gain.setValueAtTime(0, ctx.currentTime);
    }
  }

  function renderSound() {
    document.querySelectorAll(".sound-toggle").forEach(function (button) {
      button.textContent = enabled ? SOUND_ON : SOUND_OFF;
      button.setAttribute("aria-pressed", enabled ? "true" : "false");
    });
  }

  /* Recovery, or settlement "unknown", wins. The middle state is accepted, not final. */
  function badgeKind(bill) {
    if (!bill || typeof bill !== "object") return "loading";
    if (bill.recovery && typeof bill.recovery === "object") return "attention";
    if (bill.settlement === "unknown") return "attention";
    if (bill.settlement === "settled") return "settled";
    if (
      bill.settlement === "waiting-import" ||
      bill.settlement === "waiting-confirmations"
    ) {
      return "accepted";
    }
    if (bill.settlement === "broadcast") return "sent";
    return "none";
  }

  function activeStep(bill) {
    const kind = badgeKind(bill);
    if (kind === "settled" || kind === "attention" || kind === "loading") return 0;
    if (kind === "accepted" || kind === "sent") return 4;
    if (bill.pending) return 3;
    if (bill.role === "A") return 2;
    return 1;
  }

  function renderSteps(bill) {
    const labels = pack().steps;
    document.querySelectorAll("#step-rail .step-label").forEach(function (el, index) {
      el.textContent = labels[index] || "";
    });
    const step = bill ? activeStep(bill) : 0;
    const kind = bill ? badgeKind(bill) : "loading";
    document.querySelectorAll("#step-rail li").forEach(function (item, index) {
      const number = index + 1;
      const on = number === step;
      item.classList.toggle("is-active", on);
      item.classList.toggle("is-done", kind === "settled");
      if (on) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
  }

  function renderBill(bill) {
    const title = document.getElementById("pay-title");
    const section = document.getElementById("pay-state");
    if (!title || !section) return;
    lastBill = bill;
    const kind = badgeKind(bill);
    const previous = lastKind;
    const badge = pack().badges[kind] || pack().badges.none;
    section.dataset.kind = kind;
    const icon = document.getElementById("pay-icon");
    if (icon) icon.innerHTML = ICONS[kind] || ICONS.loading;
    const kicker = document.getElementById("pay-kicker");
    if (kicker) kicker.textContent = badge.kicker || "";
    title.textContent = badge.title;
    let detail = badge.detail;
    if (kind === "attention" && bill.recovery && typeof bill.recovery === "object") {
      const action = bill.recovery.action ? String(bill.recovery.action) : "";
      const endpoint = bill.recovery.endpoint ? String(bill.recovery.endpoint) : "";
      const fromApi = [action, endpoint].filter(Boolean).join(" · ");
      if (fromApi) detail = fromApi;
    } else if (kind === "none" && bill.pending && badge.pending) {
      detail = badge.pending;
    }
    const detailEl = document.getElementById("pay-detail");
    if (detailEl) detailEl.textContent = detail;
    renderSteps(bill);
    if (previous && previous !== kind && (kind === "accepted" || kind === "settled")) {
      coin();
    }
    lastKind = kind;
  }

  function fillSplash() {
    const splash = pack().splash;
    const kicker = document.getElementById("splash-kicker");
    const title = document.getElementById("splash-title");
    const body = document.getElementById("splash-body");
    const start = document.getElementById("splash-start");
    const skip = document.getElementById("splash-skip");
    if (kicker) kicker.textContent = splash.kicker;
    if (title) title.textContent = splash.title;
    if (body) body.textContent = splash.body;
    if (start) start.textContent = splash.start;
    if (skip) skip.textContent = splash.skip;
  }

  function fillLearn(nextTopic) {
    const card = pack().cards[nextTopic];
    if (!card) return false;
    topic = nextTopic;
    const kicker = document.getElementById("learn-kicker");
    const banner = document.getElementById("learn-pause");
    const title = document.getElementById("learn-title");
    const body = document.getElementById("learn-body");
    const close = document.getElementById("learn-close");
    if (kicker) kicker.textContent = pack().chrome.pauseKicker;
    if (banner) banner.textContent = pack().pauseBanner;
    if (title) title.textContent = card.title;
    if (body) {
      body.replaceChildren();
      card.paragraphs.forEach(function (text) {
        const paragraph = document.createElement("p");
        paragraph.textContent = text;
        body.appendChild(paragraph);
      });
    }
    if (close) close.textContent = pack().chrome.close;
    return true;
  }

  function fillHowto() {
    const howto = pack().howto;
    const title = document.getElementById("howto-title");
    const intro = document.getElementById("howto-intro");
    const close = document.getElementById("howto-close");
    const list = document.getElementById("howto-list");
    const openerLink = document.getElementById("howto-open");
    if (title) title.textContent = howto.title;
    if (intro) intro.textContent = howto.intro;
    if (close) close.textContent = pack().chrome.close;
    if (openerLink) openerLink.setAttribute("aria-label", pack().chrome.howtoLabel);
    if (!list) return;
    const arts = document.querySelectorAll("#howto-arts svg");
    list.replaceChildren();
    howto.steps.forEach(function (step, index) {
      const item = document.createElement("li");
      item.className = "howto-step";
      if (arts[index]) item.appendChild(arts[index].cloneNode(true));
      const text = document.createElement("div");
      const heading = document.createElement("h3");
      heading.textContent = step.title;
      const paragraph = document.createElement("p");
      paragraph.textContent = step.text;
      text.append(heading, paragraph);
      item.append(text);
      list.appendChild(item);
    });
  }

  function remember() {
    opener = document.activeElement;
  }

  function restore() {
    if (opener && typeof opener.focus === "function") opener.focus();
    opener = null;
  }

  function openLearn(nextTopic) {
    const dialog = document.getElementById("learn-dialog");
    if (!dialog || !fillLearn(nextTopic)) return;
    remember();
    if (!dialog.open) dialog.showModal();
    const title = document.getElementById("learn-title");
    if (title) title.focus();
  }

  function openHowto() {
    const dialog = document.getElementById("howto-dialog");
    if (!dialog) return;
    fillHowto();
    remember();
    if (!dialog.open) dialog.showModal();
    const title = document.getElementById("howto-title");
    if (title) title.focus();
  }

  function openSplash() {
    const splash = document.getElementById("splash");
    if (!splash || splash.open) return;
    fillSplash();
    splash.showModal();
    const start = document.getElementById("splash-start");
    if (start) start.focus();
  }

  function setLang(next) {
    if (!COPY[next]) return;
    lang = next;
    writeStore(localStorage, LANG_KEY, next);
    document.documentElement.lang = next === "es" ? "es" : "en";
    const en = document.getElementById("lang-en");
    const es = document.getElementById("lang-es");
    if (en) en.setAttribute("aria-pressed", next === "en" ? "true" : "false");
    if (es) es.setAttribute("aria-pressed", next === "es" ? "true" : "false");
    fillSplash();
    const howtoOpen = document.getElementById("howto-open");
    if (howtoOpen) howtoOpen.setAttribute("aria-label", pack().chrome.howtoLabel);
    renderSteps(lastBill);
    const learn = document.getElementById("learn-dialog");
    const howto = document.getElementById("howto-dialog");
    if (learn && learn.open && topic) fillLearn(topic);
    if (howto && howto.open) fillHowto();
    if (lastBill) renderBill(lastBill);
  }

  function splashOpen() {
    const splash = document.getElementById("splash");
    return !!(splash && splash.open);
  }

  function eventElement(event) {
    const node = event.target;
    if (node instanceof Element) return node;
    return node && node.parentElement ? node.parentElement : null;
  }

  function bind() {
    const savedLang = readStore(localStorage, LANG_KEY);
    if (savedLang === "es" || savedLang === "en") lang = savedLang;
    enabled = readStore(localStorage, SOUND_KEY) === "on";
    document.documentElement.lang = lang === "es" ? "es" : "en";
    renderSound();
    setLang(lang);

    document.addEventListener("pointerdown", function (event) {
      gesture = true;
      const hit = eventElement(event);
      if (!enabled || !hit || hit.closest("button, a")) return;
      if (splashOpen()) startLoop();
    });

    document.addEventListener("click", function (event) {
      const hit = eventElement(event);
      if (!hit) return;
      const toggle = hit.closest(".sound-toggle");
      if (toggle) {
        gesture = true;
        enabled = !enabled;
        writeStore(localStorage, SOUND_KEY, enabled ? "on" : "off");
        renderSound();
        if (enabled) {
          blip();
          if (splashOpen()) startLoop();
        } else {
          stopLoop();
        }
        return;
      }
      const learn = hit.closest("[data-learn]");
      if (learn) {
        event.preventDefault();
        openLearn(learn.getAttribute("data-learn"));
        blip();
        return;
      }
      if (hit.closest("#howto-open")) {
        event.preventDefault();
        openHowto();
        blip();
        return;
      }
      const langButton = hit.closest("#lang-en, #lang-es");
      if (langButton) {
        setLang(langButton.id === "lang-es" ? "es" : "en");
        blip();
        return;
      }
      if (hit.closest("button, a.pixel-btn")) blip();
    });

    const start = document.getElementById("splash-start");
    const skip = document.getElementById("splash-skip");
    const splash = document.getElementById("splash");
    if (start) {
      start.addEventListener("click", function () {
        gesture = true;
        stopLoop();
        if (splash) splash.close();
      });
    }
    if (skip) {
      skip.addEventListener("click", function () {
        gesture = true;
        stopLoop();
        if (splash) splash.close();
      });
    }
    if (splash) {
      splash.addEventListener("close", function () {
        writeStore(sessionStorage, SPLASH_KEY, "done");
        stopLoop();
        window.setTimeout(function () {
          if (!readStore(localStorage, HOWTO_KEY) && location.hash !== "#desk") {
            openHowto();
          }
        }, 0);
      });
    }

    const learnDialog = document.getElementById("learn-dialog");
    const learnClose = document.getElementById("learn-close");
    if (learnClose && learnDialog) {
      learnClose.addEventListener("click", function () {
        learnDialog.close();
      });
    }
    if (learnDialog) {
      learnDialog.addEventListener("close", function () {
        restore();
      });
    }

    const howtoDialog = document.getElementById("howto-dialog");
    const howtoClose = document.getElementById("howto-close");
    if (howtoClose && howtoDialog) {
      howtoClose.addEventListener("click", function () {
        howtoDialog.close();
      });
    }
    if (howtoDialog) {
      howtoDialog.addEventListener("close", function () {
        writeStore(localStorage, HOWTO_KEY, "seen");
        restore();
      });
    }

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stopLoop();
    });
  }

  function route() {
    const hash = location.hash || "";
    if (hash.indexOf("#learn=") === 0) {
      writeStore(sessionStorage, SPLASH_KEY, "done");
      let name = hash.slice("#learn=".length);
      try {
        name = decodeURIComponent(name);
      } catch (error) {
        name = "";
      }
      openLearn(name);
      return;
    }
    if (hash === "#howto") {
      writeStore(sessionStorage, SPLASH_KEY, "done");
      openHowto();
      return;
    }
    if (hash === "#desk") {
      writeStore(sessionStorage, SPLASH_KEY, "done");
      return;
    }
    if (!readStore(sessionStorage, SPLASH_KEY)) {
      openSplash();
      return;
    }
    if (!readStore(localStorage, HOWTO_KEY)) openHowto();
  }

  function boot() {
    if (!document.getElementById("pay-title") || !document.getElementById("splash")) return;
    try {
      bind();
      const help = document.getElementById("static-help");
      const howtoStatic = document.getElementById("howto-static");
      if (help) help.hidden = true;
      if (howtoStatic) howtoStatic.hidden = true;
      const icon = document.getElementById("pay-icon");
      if (icon && !icon.firstChild) icon.innerHTML = ICONS.loading;
      route();
    } catch (error) {
      /* Keep the static guide visible if the skin cannot start. */
    }
  }

  window.forkashiSkin = {
    bill: renderBill,
    coin: coin,
    buzz: buzz,
    blip: blip,
  };

  boot();
})();

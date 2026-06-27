/* ================================================================
   寺子屋すずらん 夜市ゲーム — 共通ユーティリティ
   全ゲームページでこのJSを読み込んで使用する
   ================================================================ */

'use strict';

// ----- Constants -----

const STORAGE_KEY = 'suzuran-lanterns-v1';

const LANTERN_CONFIG = {
  1: { icon: '🏮', color: 'red',    name: '赤ちょうちん',  game: '屋台スピードパズル' },
  2: { icon: '🔵', color: 'blue',   name: '青ちょうちん',  game: 'ネオンクレーン' },
  3: { icon: '💜', color: 'purple', name: '紫ちょうちん',  game: '夜店ミステリー' },
  4: { icon: '✨', color: 'gold',   name: '金ちょうちん',  game: '灯りの迷路' },
  5: { icon: '🗺️', color: 'secret', name: 'レアの灯り', game: '公園の宝物探し' },
};

// ----- URL helpers -----

function getHubUrl() {
  const path = location.pathname;
  const match = path.match(/^(.*\/suzuran-fes\/)/);
  return match
    ? location.origin + match[1]
    : location.origin + path.replace(/[^/]*$/, '');
}

// ----- Stars Background -----

function initStars(container) {
  if (!container) return;
  const frag = document.createDocumentFragment();
  for (let i = 0; i < 90; i++) {
    const el = document.createElement('div');
    el.className = 'star';
    const size = (Math.random() * 2.2 + 0.4).toFixed(1);
    el.style.cssText = [
      `width:${size}px`, `height:${size}px`,
      `left:${(Math.random() * 100).toFixed(2)}%`,
      `top:${(Math.random() * 100).toFixed(2)}%`,
      `--star-dur:${(Math.random() * 3 + 1.8).toFixed(2)}s`,
      `--star-del:${(Math.random() * 5).toFixed(2)}s`,
      `--star-lo:${(Math.random() * 0.25 + 0.08).toFixed(2)}`,
    ].join(';');
    frag.appendChild(el);
  }
  container.appendChild(frag);
}

// ----- Lantern State (localStorage) -----

function getLanterns() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; }
  catch { return []; }
}

function hasLantern(id) {
  return getLanterns().includes(Number(id));
}

function setLantern(id) {
  const list = getLanterns();
  if (list.includes(Number(id))) return false;   // already have it
  list.push(Number(id));
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  return true;   // newly collected
}

// ハブページのランタン表示を現在のlocalStorageに合わせて更新する
function updateLanternDisplay() {
  const collected = getLanterns();
  document.querySelectorAll('.lantern[data-game]').forEach(el => {
    el.classList.toggle('is-lit', collected.includes(Number(el.dataset.game)));
  });
  document.querySelectorAll('.game-card[data-game]').forEach(el => {
    el.classList.toggle('is-visited', collected.includes(Number(el.dataset.game)));
  });
}

// ----- Toast -----

let _toastEl = null;
let _toastTimer = null;

function showToast(msg, duration = 2600) {
  if (!_toastEl) {
    _toastEl = document.createElement('div');
    _toastEl.className = 'toast';
    document.body.appendChild(_toastEl);
  }
  _toastEl.textContent = msg;
  _toastEl.classList.add('is-visible');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => _toastEl.classList.remove('is-visible'), duration);
}

// ----- Game Complete Overlay -----
// 各ゲームページから呼び出す。ランタン保存→演出→ハブ or リトライを選ばせる。

function showGameComplete({ lanternId, score, extraHtml = '' }) {
  const isNew = setLantern(lanternId);
  const cfg   = LANTERN_CONFIG[lanternId] || { icon: '🏮', name: 'ちょうちん' };

  const overlay = document.createElement('div');
  overlay.className = 'game-over';
  overlay.innerHTML = `
    <div class="game-over__bg"></div>
    <div class="game-over__card">
      <span class="game-over__lantern">${cfg.icon}</span>
      <p class="game-over__headline">
        ${isNew ? cfg.name + ' ゲット！' : 'ゲームクリア！'}
      </p>
      ${score != null
        ? `<p class="game-over__score">${score}<small style="font-size:.5em;margin-left:4px">pt</small></p>`
        : ''}
      ${extraHtml}
      <div class="game-over__actions">
        <button class="btn btn--primary"   id="go-hub">🏮 灯りを確認</button>
        <button class="btn btn--secondary" id="go-retry">もう一度</button>
      </div>
    </div>`;

  document.body.appendChild(overlay);
  requestAnimationFrame(() => overlay.classList.add('is-active'));

  return new Promise(resolve => {
    overlay.querySelector('#go-hub').addEventListener('click', () => {
      location.href = getHubUrl();
    });
    overlay.querySelector('#go-retry').addEventListener('click', () => {
      overlay.classList.remove('is-active');
      setTimeout(() => { overlay.remove(); resolve('retry'); }, 320);
    });
  });
}

// ----- LINE Share -----

function shareLINE(customText) {
  const hubUrl = getHubUrl();
  const text   = customText ||
    `🏮 寺子屋すずらん の夜市ゲームで遊んでみて！\n4つのゲームで冒険しよう✨\n${hubUrl}`;
  const lineUrl = `https://line.me/R/msg/text/?${encodeURIComponent(text)}`;
  if (/Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
    location.href = lineUrl;
  } else {
    window.open(lineUrl, '_blank', 'noopener,noreferrer');
  }
}

// ----- Combo animation helper -----
// el: DOMElement, value: number → 表示を更新しポップアニメを発火

function updateCombo(el, value) {
  if (!el) return;
  el.textContent = value > 1 ? `${value} COMBO!` : '';
  if (value > 1) {
    el.classList.remove('combo--pop');
    void el.offsetWidth;  // reflow to restart animation
    el.classList.add('combo--pop');
  }
}

// ----- Timer helper -----
// onTick(remaining): 毎秒呼ばれる / onEnd(): 0になったとき呼ばれる

function createTimer(seconds, onTick, onEnd) {
  let remaining = seconds;
  let id = null;

  function tick() {
    onTick(remaining);
    if (remaining <= 0) { clearInterval(id); onEnd(); return; }
    remaining--;
  }

  return {
    start() { tick(); id = setInterval(tick, 1000); },
    stop()  { clearInterval(id); },
    get remaining() { return remaining; },
  };
}

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function read(relative) {
  return readFileSync(resolve(root, relative), "utf8");
}

const baseCss = read("src/style.css")
  .replace(/@import url\([^)]+\);\n*/, "")
  .split(".player-shell")[0];

const extraCss = `
html, body { min-height: 100%; }
.hidden { display: none !important; }
.eyebrow {
  margin: 0 0 12px;
  color: var(--orange);
  font: 500 10px/1 "DM Mono", ui-monospace, monospace;
  letter-spacing: .2em;
}
h1 { margin: 0; font-size: clamp(30px, 4.1vw, 52px); line-height: 1.15; letter-spacing: -.055em; }
h1 em { color: var(--orange); font-style: normal; }
.empty-copy { color: var(--muted); font-size: 13px; margin: 15px 0 23px; }
.primary-button, .secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  min-height: 42px;
  padding: 0 20px;
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}
.primary-button { background: var(--orange); color: #fff; }
.primary-button:hover { background: var(--orange-bright); }
.secondary-button { border-color: rgba(255,255,255,.16); background: rgba(255,255,255,.04); }
.secondary-button:hover { background: rgba(255,255,255,.09); }
.toast {
  position: absolute; z-index: 5; top: 20px; left: 50%; transform: translateX(-50%);
  padding: 10px 15px; border: 1px solid var(--line); background: rgba(26,26,24,.94);
  box-shadow: 0 8px 30px rgba(0,0,0,.4); color: #deddd7; font-size: 12px;
}
.toast.error { border-color: rgba(255,91,27,.45); }
footer {
  display: flex; justify-content: space-between; padding: 24px 34px; border-top: 1px solid var(--line);
  color: #5d5d58; font: 400 9px "DM Mono", ui-monospace, monospace; letter-spacing: .1em;
}
dialog { width: min(500px, calc(100% - 32px)); border: 1px solid rgba(255,255,255,.13); padding: 0; color: #eee; background: #1a1a18; box-shadow: 0 24px 100px rgba(0,0,0,.65); }
dialog::backdrop { background: rgba(0,0,0,.75); backdrop-filter: blur(5px); }
.dialog-content { position: relative; display: flex; flex-direction: column; padding: 34px; }
.dialog-content h2 { margin: 0; font-size: 24px; }
.dialog-close { position: absolute; top: 15px; right: 15px; border: 0; background: transparent; color: #888; font-size: 24px; cursor: pointer; }
.help-content dl { margin: 20px 0 0; }
.help-content dl div { display: flex; justify-content: space-between; padding: 13px 0; border-top: 1px solid var(--line); }
.help-content dt { font: 500 11px "DM Mono", ui-monospace, monospace; color: var(--orange); }
.help-content dd { margin: 0; color: #aaa; font-size: 11px; }
@media (max-width: 720px) {
  .topbar { grid-template-columns: 1fr auto; padding: 0 18px; }
  .source-state, .tool-nav { display: none; }
  main { width: calc(100% - 24px); margin-top: 22px; }
  footer { padding-inline: 18px; }
}
`;

const css = [
  baseCss.replace(
    'font-family: "Noto Sans TC", sans-serif;',
    'font-family: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", sans-serif;',
  ),
  extraCss,
  read("src/mipi-raw.css"),
].join("\n");

const convertJs = read("src/mipi-raw/convert.js").replaceAll(/^export /gm, "");
const uiJs = read("src/mipi-raw-ui.js").replace(/^import[\s\S]*?;\n/gm, "");

const html = `<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#121211" />
    <title>MIPI RAW10 轉換器</title>
    <style>
${css}
    </style>
  </head>
  <body>
    <div id="app">
      <header class="topbar">
        <span class="brand" aria-label="Optic">
          <span class="brand-mark" aria-hidden="true">
            <span></span><span></span><span></span>
          </span>
          <span>OPTIC</span>
        </span>
        <div class="source-state">
          <span class="status-dot"></span>
          <span id="sourceLabel">尚未載入 RAW</span>
        </div>
        <div class="topbar-actions">
          <button class="icon-button" id="helpButton" aria-label="使用說明" title="使用說明">?</button>
        </div>
      </header>

      <main>
        <section class="converter-layout" aria-label="MIPI RAW10 轉換器">
          <aside class="control-panel">
            <p class="eyebrow">MIPI RAW10</p>
            <h2>10-bit RAW 轉圖</h2>
            <div class="drop-zone" id="dropZone" role="button" tabindex="0">
              <strong>拖放 RAW 檔到這裡</strong>
              <small>支援 .raw / .RAW10 / 任意二進位 dump</small>
            </div>
            <p class="file-meta" id="fileMeta"></p>
            <div class="button-row">
              <button class="primary-button" id="openFileButton" type="button">開啟檔案</button>
              <button class="secondary-button" id="sampleButton" type="button">載入示範畫面</button>
            </div>
            <div class="panel-scroll">
            <div class="field-grid">
              <label class="field span-2">
                <span>可能的解析度</span>
                <select id="guessSelect">
                  <option value="">載入檔案後自動猜測</option>
                </select>
              </label>
              <label class="field">
                <span>寬度</span>
                <input id="width" type="number" min="8" step="4" placeholder="1920" />
              </label>
              <label class="field">
                <span>高度</span>
                <input id="height" type="number" min="8" step="1" placeholder="1080" />
              </label>
              <label class="field">
                <span>封包格式</span>
                <select id="format">
                  <option value="mipi10">MIPI RAW10（4 像素 / 5 bytes）</option>
                  <option value="u16le">Unpacked 16-bit LE（低 10 bit）</option>
                  <option value="u16msb">Unpacked 16-bit LE（高 10 bit）</option>
                  <option value="u16be">Unpacked 16-bit BE</option>
                </select>
              </label>
              <label class="field">
                <span>Bayer 排列</span>
                <select id="bayer">
                  <option value="RGGB">RGGB</option>
                  <option value="GRBG">GRBG</option>
                  <option value="GBRG">GBRG</option>
                  <option value="BGGR">BGGR</option>
                  <option value="mono">Mono（灰階）</option>
                </select>
              </label>
              <label class="field">
                <span>檔頭 offset</span>
                <input id="offset" type="number" min="0" step="1" value="0" />
              </label>
              <label class="field">
                <span>列跨距 stride</span>
                <input id="stride" type="number" min="0" step="1" placeholder="自動" />
              </label>
              <label class="field">
                <span>影格</span>
                <input id="frame" type="number" min="0" step="1" value="0" />
              </label>
              <label class="field">
                <span>黑電平</span>
                <input id="blackLevel" type="number" min="0" max="1023" step="1" value="0" />
              </label>
              <label class="field">
                <span>白平衡</span>
                <select id="whiteBalance">
                  <option value="auto">自動（灰世界）</option>
                  <option value="off">關閉</option>
                </select>
              </label>
              <label class="field">
                <span>10-bit → 8-bit</span>
                <select id="tone">
                  <option value="percentile">百分位拉伸（較好看）</option>
                  <option value="shift">直接右移 2 bit</option>
                  <option value="stretch">最小-最大拉伸</option>
                </select>
              </label>
              <label class="field">
                <span>JPEG 品質</span>
                <input id="jpegQuality" type="number" min="40" max="95" step="1" value="92" />
              </label>
            </div>
            </div>
            <div class="panel-actions">
              <div class="button-row">
                <button class="primary-button" id="convertButton" type="button">轉換預覽</button>
              </div>
              <div class="save-row">
                <button class="secondary-button" data-save="png" type="button" disabled>PNG</button>
                <button class="secondary-button" data-save="jpeg" type="button" disabled>JPG</button>
                <button class="secondary-button" data-save="bmp" type="button" disabled>BMP</button>
              </div>
              <p class="hint">雙擊這個 HTML 就能用，不必安裝 Node。轉換在瀏覽器本機完成，檔案不會上傳。</p>
            </div>
          </aside>
          <section class="preview-panel">
            <div class="preview-wrap" id="previewWrap">
              <div class="preview-empty" id="emptyPreview">
                <p class="eyebrow">READY TO CONVERT</p>
                <h1>把 RAW<br /><em>變成圖片。</em></h1>
                <p class="empty-copy">載入 sensor dump，或先用示範色卡確認 Bayer 排列。</p>
              </div>
              <canvas id="preview" aria-label="轉換預覽"></canvas>
              <div class="toast hidden" id="toast" role="status"></div>
            </div>
          </section>
        </section>
      </main>
      <footer>
        <span>OPTIC RAW10</span>
        <span>直接開啟本檔即可使用</span>
      </footer>
    </div>
    <input id="fileInput" type="file" accept=".raw,.RAW,.raw10,.RAW10,.bin,.img,*" hidden />
    <dialog id="helpDialog">
      <div class="dialog-content help-content">
        <button class="dialog-close" id="helpCloseButton" aria-label="關閉">×</button>
        <p class="eyebrow">HOW TO USE</p>
        <h2>使用方式</h2>
        <dl>
          <div><dt>1</dt><dd>雙擊 mipi-raw.html 用瀏覽器開啟</dd></div>
          <div><dt>2</dt><dd>拖入 .raw，或按「載入示範畫面」</dd></div>
          <div><dt>3</dt><dd>確認寬高與 Bayer 後，下載 PNG / JPG / BMP</dd></div>
        </dl>
      </div>
    </dialog>
    <script>
${convertJs}

${uiJs}
    </script>
  </body>
</html>
`;

const target = resolve(root, "mipi-raw.html");
writeFileSync(target, html);
console.log(`wrote ${target} (${html.length} bytes)`);

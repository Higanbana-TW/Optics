# Optic Player

一個受 VLC 啟發的輕量網頁播放器，支援：

- 本機 MP4、WebM、Ogg 與瀏覽器可解碼的影音格式
- HTTP(S) 影音網址與 HLS (`.m3u8`) 網路串流
- 播放、暫停、快轉、倒退、音量、倍速與全螢幕控制
- 將目前影格以原始解析度擷取為 PNG

## 開發

```bash
npm install
npm run dev
```

建立正式版本：

```bash
npm run build
```

> 網路串流需允許瀏覽器跨來源存取（CORS）。RTSP、DRM 內容與瀏覽器不支援的編碼無法直接播放。

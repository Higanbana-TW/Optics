Windows 預覽版。不需要安裝 Python。

1. 下載並解壓縮 `LiveCaptions-windows.zip`
2. 打開裡面的 `LiveCaptions` 資料夾
3. 雙擊 `LiveCaptions.exe`

字幕列會先出現。第一次開啟需要網路，程式接著下載語音模型（約 139 MB）和翻譯模型（約 68 MB）。這兩個模型沒有包進壓縮檔。

結束：系統匣的「字」圖示，或 `Ctrl+Alt+Q`。拖曳可移動。`Ctrl+Alt+C` 點擊穿透，`Ctrl+Alt+H` 隱藏，`Ctrl+Alt+A` 切換系統播放與麥克風。

這個 exe 是在 GitHub Actions 的 `windows-latest` 上用 PyInstaller（onedir）建置的。

# Optics

## Lens distortion 長方形逆向預變形 Excel 計算器

[`lens_distortion_line_calculator.xlsx`](lens_distortion_line_calculator.xlsx) 以 sensor 上希望得到的正常長方形為目標，反算物方應製作的預變形邊界：

- 最多 2000 筆半視角／Optical distortion (%) 資料
- Sensor pixel size、EFL、物方平面至入瞳距離及光軸中心
- Sensor 目標長方形的中心、寬、高與旋轉角

工作表會輸出物方預變形的四角座標，以及每邊最多 50 段的完整曲邊座標。內建正向投影驗證、pixel 誤差及 sensor／物方圖形。詳細座標定義、畸變符號與模型限制請見檔案內「使用說明」頁。

重新產生檔案：

```bash
python3 -m pip install openpyxl
python3 generate_lens_distortion_excel.py
```

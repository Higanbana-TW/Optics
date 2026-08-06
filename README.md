# Optics

## 西門子星產生器

`siemens_star.py` 使用 Python 標準函式庫產生可按實際尺寸列印的 SVG，
不需安裝額外套件。

### 使用方式

產生每區隔 2°、A4 直向版本：

```bash
python3 siemens_star.py --angle 2 --paper A4 -o siemens_star_a4_2deg.svg
```

產生每區隔 5°、A3 橫向版本：

```bash
python3 siemens_star.py \
  --angle 5 \
  --paper A3 \
  --orientation landscape \
  -o siemens_star_a3_5deg.svg
```

可用參數：

- `--angle`：每個黑色或白色區隔的角度；角度必須能整除 360°，例如 `2` 或 `5`
- `--paper`：`A4` 或 `A3`
- `--orientation`：`portrait`（直向）或 `landscape`（橫向）
- `--margin`：紙張邊界，單位 mm，預設 `10`
- `--radius`：指定星形半徑，單位 mm；省略時使用邊界內的最大尺寸
- `-o` / `--output`：輸出檔案名稱

請用瀏覽器、Inkscape 或其他向量軟體開啟 SVG。列印時選擇
「實際大小」或 `100%`，並關閉「符合頁面」，以維持正確實體尺寸。

### 測試

```bash
python3 -m unittest -v
```

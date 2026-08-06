# Optics

## 西門子星產生器

`siemens_star.py` 使用 Python 標準函式庫產生可按實際尺寸列印的 SVG，
不需安裝額外套件。

### 使用方式

產生每區隔 2°、佈滿整張 A4 的直向版本：

```bash
python3 siemens_star.py --angle 2 --paper A4 -o siemens_star_a4_2deg.svg
```

產生每區隔 5°、佈滿整張 A3 的橫向版本：

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
- `--circle`：改成傳統圓形版本；未指定時，放射區塊會延伸並佈滿整張紙
- `--margin`：圓形模式的紙張邊界，單位 mm，預設 `10`
- `--radius`：圓形模式的自訂半徑，單位 mm，必須搭配 `--circle`
- `-o` / `--output`：輸出檔案名稱

如需傳統圓形版本：

```bash
python3 siemens_star.py --angle 5 --paper A4 --circle -o circular_star.svg
```

請用瀏覽器、Inkscape 或其他向量軟體開啟 SVG。列印時選擇
「實際大小」或 `100%`，並關閉「符合頁面」，以維持正確實體尺寸。

### 測試

```bash
python3 -m unittest -v
```

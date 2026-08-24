# EIAJ / ITE Test Chart A (DXF)

Native **4:3** resolution chart (EIA 1956 / EIAJ Test Chart A / ITE Resolution Chart). Circles stay round. Wedge numbers are **TV lines (200–800)**, not ISO 12233 LW/PH.

This is a geometric recreation for workshop printing, not an ITE-certified manufactured target. Source vector is the public-domain Wikimedia file `EIA_Resolution_Chart_1956.svg`.

## Size

ITE 1X valid area is **240 × 180 mm**. `--scale 4` is **960 × 720 mm**.

ISO 12233 4× uses 800 mm picture height; that is a different standard and a 16:9 plate. Do not mix the two when comparing 本数.

## Generate

```bash
python3 tools/eiaj/generate.py --scale 4 --preview
```

Output: `tools/eiaj/output/eiaj_4x3_4x_full.dxf`

# Sources

- ISO 12233:2000 feature list (public descriptions of elements A–T: hyperbolic wedges, slanted-edge SFR, framing arrows, LW/PH units).
- Public vector recreation by Stephen H. Westin, Cornell University:
  https://www.graphics.cornell.edu/~westin/misc/res-chart.html
- CIPA notes that Chart 1 (ISO 12233:2000) is 16:9; the later CIPA chart is 3:2. The 2000 plate’s 4:3 arrows mark a crop of that 16:9 layout. Native 4:3 DXFs keep feature shapes and translate the four corner crosses so their KS plus centres sit at the EIAJ / ITE Test Chart A corner-circle field points (nx=0.762 of 4:3 half-width, ny=0.676 of 4:3 half-height, measured from `tools/eiaj/data/eiaj_1956.svg`). Overlapping centre wedges and square-wave sweeps are omitted; diamond, square, and parallelogram SFR patches remain. The centre zone plate is not moved or scaled. EIAJ TVL labels are not copied.
- 1X active height is 200 mm (ISO minimum for reflective charts). 4X uses 800 mm active height.
- 4K (`--4k`) 本数 follow the **2× Enhanced I3A/ISO 12233** printed scale on Edmund Optics drawing 58-941 (Applied Image QA-77, pattern 400×711 mm). That PDF is marked for information only / do not manufacture; this generator does not copy QA-77 extras (extra star sectors, gray SFR diamonds, branding). Only the Cornell 2000 geometry is redrawn, with per-wedge pitch and O/P densify so labels match that Enhanced scale.

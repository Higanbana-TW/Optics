const paperSizes = {
  A4: [210, 297],
  A3: [297, 420],
};

function pageSettings(angle, paper, orientation) {
  let [width, height] = paperSizes[paper];
  if (orientation === "landscape") [width, height] = [height, width];
  return { paper, angle: Number(angle), width, height, orientation };
}

function formatNumber(value) {
  const text = value.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  return text.includes(".") ? text : `${text}.0`;
}

function dxfPair(code, value) {
  return `${String(code).padStart(3, " ")}\r\n${value}`;
}

function dxfPairs(entries) {
  return entries.map(([code, value]) => dxfPair(code, value)).join("\r\n");
}

function clipEdge(points, inside, intersection) {
  const output = [];
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    const previous = points[(index + points.length - 1) % points.length];
    const currentInside = inside(current);
    const previousInside = inside(previous);
    if (currentInside) {
      if (!previousInside) output.push(intersection(previous, current));
      output.push(current);
    } else if (previousInside) {
      output.push(intersection(previous, current));
    }
  }
  return output;
}

function clipToPage(points, width, height) {
  let result = points;
  result = clipEdge(
    result,
    point => point[0] >= 0,
    (from, to) => {
      const ratio = (0 - from[0]) / (to[0] - from[0]);
      return [0, from[1] + ratio * (to[1] - from[1])];
    }
  );
  result = clipEdge(
    result,
    point => point[0] <= width,
    (from, to) => {
      const ratio = (width - from[0]) / (to[0] - from[0]);
      return [width, from[1] + ratio * (to[1] - from[1])];
    }
  );
  result = clipEdge(
    result,
    point => point[1] >= 0,
    (from, to) => {
      const ratio = (0 - from[1]) / (to[1] - from[1]);
      return [from[0] + ratio * (to[0] - from[0]), 0];
    }
  );
  return clipEdge(
    result,
    point => point[1] <= height,
    (from, to) => {
      const ratio = (height - from[1]) / (to[1] - from[1]);
      return [from[0] + ratio * (to[0] - from[0]), height];
    }
  );
}

function createBlackPolygons(settings) {
  const { angle, width, height } = settings;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.hypot(width, height) * 2;
  const sectorCount = Math.round(360 / angle);
  const polygons = [];

  for (let index = 0; index < sectorCount; index += 2) {
    const start = (-90 + index * angle) * Math.PI / 180;
    const end = (-90 + (index + 1) * angle) * Math.PI / 180;
    polygons.push(clipToPage([
      [centerX, centerY],
      [centerX + radius * Math.cos(start), centerY + radius * Math.sin(start)],
      [centerX + radius * Math.cos(end), centerY + radius * Math.sin(end)],
    ], width, height));
  }
  return polygons;
}

function createSvg(settings) {
  const { paper, angle, width, height, orientation } = settings;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.hypot(width, height);
  const sectorCount = Math.round(360 / angle);
  const paths = [];

  for (let index = 0; index < sectorCount; index += 2) {
    const start = (-90 + index * angle) * Math.PI / 180;
    const end = (-90 + (index + 1) * angle) * Math.PI / 180;
    const x1 = centerX + radius * Math.cos(start);
    const y1 = centerY + radius * Math.sin(start);
    const x2 = centerX + radius * Math.cos(end);
    const y2 = centerY + radius * Math.sin(end);
    paths.push(
      `<path d="M ${formatNumber(centerX)} ${formatNumber(centerY)} ` +
      `L ${formatNumber(x1)} ${formatNumber(y1)} ` +
      `A ${formatNumber(radius)} ${formatNumber(radius)} 0 0 1 ` +
      `${formatNumber(x2)} ${formatNumber(y2)} Z"/>`
    );
  }

  const title = `Siemens star: ${angle} degree sectors, ${paper}, ${orientation}`;
  return `<svg xmlns="http://www.w3.org/2000/svg" ` +
    `width="${width}mm" height="${height}mm" ` +
    `viewBox="0 0 ${width} ${height}" role="img" aria-label="${title}">` +
    `<title>${title}</title>` +
    `<defs><clipPath id="paper-clip">` +
    `<rect width="${width}" height="${height}"/></clipPath></defs>` +
    `<rect width="${width}" height="${height}" fill="white"/>` +
    `<g fill="black" shape-rendering="geometricPrecision" ` +
    `clip-path="url(#paper-clip)">${paths.join("")}</g></svg>`;
}

function createDxf(settings) {
  const { width, height } = settings;
  const centerX = width / 2;
  const centerY = height / 2;
  const sections = [
    dxfPairs([
      [0, "SECTION"], [2, "HEADER"],
      [9, "$ACADVER"], [1, "AC1009"],
      [9, "$INSBASE"], [10, "0.0"], [20, "0.0"], [30, "0.0"],
      [9, "$EXTMIN"], [10, "0.0"], [20, "0.0"], [30, "0.0"],
      [9, "$EXTMAX"],
      [10, formatNumber(width)], [20, formatNumber(height)], [30, "0.0"],
      [9, "$LIMMIN"], [10, "0.0"], [20, "0.0"],
      [9, "$LIMMAX"],
      [10, formatNumber(width)], [20, formatNumber(height)],
      [9, "$FILLMODE"], [70, "1"],
      [9, "$HANDLING"], [70, "0"],
      [0, "ENDSEC"],
      [0, "SECTION"], [2, "TABLES"],
      [0, "TABLE"], [2, "VPORT"], [70, "1"],
      [0, "VPORT"], [2, "*ACTIVE"], [70, "0"],
      [10, "0.0"], [20, "0.0"],
      [11, "1.0"], [21, "1.0"],
      [12, formatNumber(centerX)], [22, formatNumber(centerY)],
      [13, "0.0"], [23, "0.0"],
      [14, "1.0"], [24, "1.0"],
      [15, "1.0"], [25, "1.0"],
      [16, "0.0"], [26, "0.0"], [36, "1.0"],
      [17, "0.0"], [27, "0.0"], [37, "0.0"],
      [40, formatNumber(height)], [41, formatNumber(width / height)],
      [42, "50.0"], [43, "0.0"], [44, "0.0"],
      [50, "0.0"], [51, "0.0"],
      [71, "0"], [72, "100"], [73, "1"], [74, "3"],
      [75, "0"], [76, "0"], [77, "0"], [78, "0"],
      [0, "ENDTAB"],
      [0, "TABLE"], [2, "LTYPE"], [70, "1"],
      [0, "LTYPE"], [2, "CONTINUOUS"], [70, "0"], [3, "Solid line"],
      [72, "65"], [73, "0"], [40, "0.0"],
      [0, "ENDTAB"],
      [0, "TABLE"], [2, "LAYER"], [70, "2"],
      [0, "LAYER"], [2, "0"], [70, "0"], [62, "7"], [6, "CONTINUOUS"],
      [0, "LAYER"], [2, "SIEMENS_STAR"], [70, "0"], [62, "7"], [6, "CONTINUOUS"],
      [0, "ENDTAB"],
      [0, "TABLE"], [2, "STYLE"], [70, "1"],
      [0, "STYLE"], [2, "STANDARD"], [70, "0"],
      [40, "0.0"], [41, "1.0"], [50, "0.0"], [71, "0"], [42, "2.5"],
      [3, "txt"], [4, ""],
      [0, "ENDTAB"],
      [0, "TABLE"], [2, "VIEW"], [70, "0"], [0, "ENDTAB"],
      [0, "TABLE"], [2, "UCS"], [70, "0"], [0, "ENDTAB"],
      [0, "TABLE"], [2, "APPID"], [70, "1"],
      [0, "APPID"], [2, "ACAD"], [70, "0"],
      [0, "ENDTAB"],
      [0, "TABLE"], [2, "DIMSTYLE"], [70, "0"], [0, "ENDTAB"],
      [0, "ENDSEC"],
      [0, "SECTION"], [2, "BLOCKS"], [0, "ENDSEC"],
      [0, "SECTION"], [2, "ENTITIES"],
    ]),
  ];

  for (const polygon of createBlackPolygons(settings)) {
    for (let index = 1; index < polygon.length - 1; index += 1) {
      const [first, second, third] = [
        polygon[0],
        polygon[index],
        polygon[index + 1],
      ].map(([x, y]) => [x, height - y]);
      sections.push(dxfPairs([
        [0, "SOLID"], [8, "SIEMENS_STAR"], [62, "7"],
        [10, formatNumber(first[0])], [20, formatNumber(first[1])], [30, "0.0"],
        [11, formatNumber(second[0])], [21, formatNumber(second[1])], [31, "0.0"],
        [12, formatNumber(third[0])], [22, formatNumber(third[1])], [32, "0.0"],
        [13, formatNumber(third[0])], [23, formatNumber(third[1])], [33, "0.0"],
      ]));
    }
  }

  sections.push(dxfPairs([[0, "ENDSEC"], [0, "EOF"]]));
  return `${sections.join("\r\n")}\r\n`;
}

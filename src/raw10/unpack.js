import { bytesPerRow, isPacked } from "./format.js";

/**
 * Decode one frame of MIPI/unpacked 10-bit RAW into 0..1023 samples.
 *
 * MIPI CSI-2 RAW10 stores four pixels in five bytes: the first four bytes hold
 * bits 9:2 of each pixel and the fifth byte packs the four pairs of low bits.
 * Some vendors emit the low-bit pairs in the opposite order, which is what the
 * `mipi10lsbrev` packing handles.
 */
export function unpackFrame(bytes, options) {
  const { width, height, packing = "mipi10", align = "lsb" } = options;
  if (!(width > 0) || !(height > 0)) throw new Error("width and height must be positive");

  const stride = options.stride > 0 ? options.stride : bytesPerRow(width, packing);
  const offset = options.offset > 0 ? options.offset : 0;
  const out = new Uint16Array(width * height);

  if (!isPacked(packing)) {
    const bigEndian = packing === "raw16be";
    const shift = align === "msb" ? 6 : 0;
    for (let y = 0; y < height; y += 1) {
      const rowStart = offset + y * stride;
      const dstRow = y * width;
      for (let x = 0; x < width; x += 1) {
        const i = rowStart + x * 2;
        if (i + 1 >= bytes.length) return out;
        const value = bigEndian ? (bytes[i] << 8) | bytes[i + 1] : bytes[i] | (bytes[i + 1] << 8);
        out[dstRow + x] = (value >> shift) & 0x3ff;
      }
    }
    return out;
  }

  const reversed = packing === "mipi10lsbrev";
  for (let y = 0; y < height; y += 1) {
    let src = offset + y * stride;
    const dstRow = y * width;
    for (let x = 0; x < width; src += 5) {
      if (src + 4 >= bytes.length) return out;
      const low = bytes[src + 4];
      for (let k = 0; k < 4 && x < width; k += 1, x += 1) {
        const lsb = reversed ? (low >> (6 - 2 * k)) & 3 : (low >> (2 * k)) & 3;
        out[dstRow + x] = (bytes[src + k] << 2) | lsb;
      }
    }
  }
  return out;
}

/** Inverse of {@link unpackFrame}; used by the sample generator and the tests. */
export function packFrame(samples, options) {
  const { width, height, packing = "mipi10", align = "lsb" } = options;
  const stride = options.stride > 0 ? options.stride : bytesPerRow(width, packing);
  const bytes = new Uint8Array(stride * height);

  if (!isPacked(packing)) {
    const bigEndian = packing === "raw16be";
    const shift = align === "msb" ? 6 : 0;
    for (let y = 0; y < height; y += 1) {
      const rowStart = y * stride;
      const srcRow = y * width;
      for (let x = 0; x < width; x += 1) {
        const value = (samples[srcRow + x] & 0x3ff) << shift;
        const i = rowStart + x * 2;
        bytes[i] = bigEndian ? (value >> 8) & 0xff : value & 0xff;
        bytes[i + 1] = bigEndian ? value & 0xff : (value >> 8) & 0xff;
      }
    }
    return bytes;
  }

  const reversed = packing === "mipi10lsbrev";
  for (let y = 0; y < height; y += 1) {
    let dst = y * stride;
    const srcRow = y * width;
    for (let x = 0; x < width; dst += 5) {
      let low = 0;
      for (let k = 0; k < 4 && x < width; k += 1, x += 1) {
        const value = samples[srcRow + x] & 0x3ff;
        bytes[dst + k] = value >> 2;
        low |= (value & 3) << (reversed ? 6 - 2 * k : 2 * k);
      }
      bytes[dst + 4] = low;
    }
  }
  return bytes;
}

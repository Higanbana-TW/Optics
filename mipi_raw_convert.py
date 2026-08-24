#!/usr/bin/env python3
"""Convert 10-bit MIPI CSI-2 RAW dumps to BMP, JPEG, or PNG.

MIPI RAW10 packs four 10-bit pixels into five bytes (CSI-2):

    byte0 = P0[9:2]
    byte1 = P1[9:2]
    byte2 = P2[9:2]
    byte3 = P3[9:2]
    byte4 = P3[1:0] P2[1:0] P1[1:0] P0[1:0]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


PACKED_BYTES_PER_PIXEL = 5 / 4
UNPACKED_BYTES_PER_PIXEL = 2
BIT_DEPTH = 10
MAX_10BIT = (1 << BIT_DEPTH) - 1

BAYER_PATTERNS = ("RGGB", "GRBG", "GBRG", "BGGR")
TONE_MAPS = ("shift", "stretch", "percentile")
IMAGE_FORMATS = {
    ".bmp": "BMP",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
}

COMMON_RESOLUTIONS = (
    (320, 240),
    (640, 480),
    (800, 600),
    (1024, 768),
    (1280, 720),
    (1280, 800),
    (1280, 960),
    (1440, 1080),
    (1600, 1200),
    (1632, 1224),
    (1920, 1080),
    (1920, 1200),
    (2048, 1536),
    (2304, 1296),
    (2304, 1536),
    (2304, 1728),
    (2560, 1440),
    (2592, 1944),
    (3264, 1836),
    (3264, 2448),
    (3280, 2464),
    (3840, 2160),
    (4000, 3000),
    (4032, 2268),
    (4032, 3024),
    (4056, 3040),
    (4096, 2160),
    (4096, 3072),
    (4208, 3120),
    (4624, 2604),
    (4624, 3472),
    (4656, 3496),
    (5344, 4016),
    (8000, 6000),
    (9152, 6944),
    (9248, 6944),
)

ASPECT_RATIOS = ((16, 9), (16, 10), (4, 3), (3, 2), (5, 4), (1, 1), (21, 9))


class RawConvertError(ValueError):
    """User-facing conversion error."""


def packed_row_bytes(width: int) -> int:
    if width % 4:
        raise RawConvertError("MIPI RAW10 寬度必須是 4 的倍數")
    return width * 5 // 4


def pack_raw10_mipi(pixels: np.ndarray) -> bytes:
    """Pack a uint16 image (10-bit values) into CSI-2 RAW10 bytes."""
    if pixels.ndim != 2:
        raise RawConvertError("打包來源必須是單通道影像")
    height, width = pixels.shape
    row_bytes = packed_row_bytes(width)
    groups = pixels.reshape(height, width // 4, 4).astype(np.uint16)
    packed = np.empty((height, width // 4, 5), dtype=np.uint8)
    packed[:, :, 0] = (groups[:, :, 0] >> 2) & 0xFF
    packed[:, :, 1] = (groups[:, :, 1] >> 2) & 0xFF
    packed[:, :, 2] = (groups[:, :, 2] >> 2) & 0xFF
    packed[:, :, 3] = (groups[:, :, 3] >> 2) & 0xFF
    packed[:, :, 4] = (
        (groups[:, :, 0] & 0x03)
        | ((groups[:, :, 1] & 0x03) << 2)
        | ((groups[:, :, 2] & 0x03) << 4)
        | ((groups[:, :, 3] & 0x03) << 6)
    )
    if packed.reshape(height, row_bytes).shape[1] != row_bytes:
        raise RawConvertError("MIPI RAW10 打包列長不一致")
    return packed.reshape(-1).tobytes()


def unpack_raw10_mipi(
    data: bytes | np.ndarray,
    width: int,
    height: int,
    *,
    offset: int = 0,
    stride: int | None = None,
) -> np.ndarray:
    """Unpack CSI-2 RAW10 into a uint16 array of shape (height, width)."""
    row_bytes = packed_row_bytes(width)
    stride = row_bytes if stride is None else stride
    if stride < row_bytes:
        raise RawConvertError(f"列跨距 {stride} 小於 RAW10 列長 {row_bytes}")

    payload = np.frombuffer(data, dtype=np.uint8, offset=offset)
    needed = stride * height
    if payload.size < needed:
        raise RawConvertError(
            f"檔案資料不足：需要 {needed + offset} bytes，實際 {len(data)} bytes"
        )

    if stride == row_bytes:
        rows = payload[:needed].reshape(height, width // 4, 5)
    else:
        rows = payload[:needed].reshape(height, stride)[:, :row_bytes].reshape(
            height, width // 4, 5
        )

    pixels = np.empty((height, width // 4, 4), dtype=np.uint16)
    lsb = rows[:, :, 4].astype(np.uint16)
    pixels[:, :, 0] = (rows[:, :, 0].astype(np.uint16) << 2) | (lsb & 0x03)
    pixels[:, :, 1] = (rows[:, :, 1].astype(np.uint16) << 2) | ((lsb >> 2) & 0x03)
    pixels[:, :, 2] = (rows[:, :, 2].astype(np.uint16) << 2) | ((lsb >> 4) & 0x03)
    pixels[:, :, 3] = (rows[:, :, 3].astype(np.uint16) << 2) | ((lsb >> 6) & 0x03)
    return pixels.reshape(height, width)


def unpack_u16(
    data: bytes | np.ndarray,
    width: int,
    height: int,
    *,
    offset: int = 0,
    stride: int | None = None,
    endian: str = "<",
    msb_aligned: bool = False,
) -> np.ndarray:
    """Unpack 16-bit little/big-endian pixels holding 10-bit samples."""
    dtype = np.dtype(f"{endian}u2")
    row_bytes = width * 2
    stride = row_bytes if stride is None else stride
    if stride < row_bytes:
        raise RawConvertError(f"列跨距 {stride} 小於 16-bit 列長 {row_bytes}")
    if stride % 2:
        raise RawConvertError("16-bit RAW 的列跨距必須是偶數")

    payload = np.frombuffer(data, dtype=np.uint8, offset=offset)
    needed = stride * height
    if payload.size < needed:
        raise RawConvertError(
            f"檔案資料不足：需要 {needed + offset} bytes，實際 {len(data)} bytes"
        )

    if stride == row_bytes:
        values = np.frombuffer(payload[:needed].tobytes(), dtype=dtype).reshape(height, width)
    else:
        row_view = payload[:needed].reshape(height, stride)[:, :row_bytes]
        values = np.frombuffer(np.ascontiguousarray(row_view).tobytes(), dtype=dtype).reshape(
            height, width
        )

    if msb_aligned:
        values = values >> (16 - BIT_DEPTH)
    return values.astype(np.uint16, copy=False) & MAX_10BIT


def mosaic_bayer(rgb: np.ndarray, pattern: str = "RGGB") -> np.ndarray:
    """Downsample an RGB image to a Bayer CFA (10-bit uint16)."""
    pattern = pattern.upper()
    if pattern not in BAYER_PATTERNS:
        raise RawConvertError(f"不支援的 Bayer 排列：{pattern}")
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise RawConvertError("馬賽克來源必須是 RGB 影像")

    height, width, _ = rgb.shape
    raw = np.empty((height, width), dtype=np.uint16)
    channel = {
        "RGGB": np.array([[0, 1], [1, 2]], dtype=np.int8),
        "GRBG": np.array([[1, 0], [2, 1]], dtype=np.int8),
        "GBRG": np.array([[1, 2], [0, 1]], dtype=np.int8),
        "BGGR": np.array([[2, 1], [1, 0]], dtype=np.int8),
    }[pattern]
    yy, xx = np.indices((height, width))
    raw[:, :] = rgb[yy, xx, channel[yy & 1, xx & 1]]
    return raw


def _neighbors4(plane: np.ndarray) -> np.ndarray:
    padded = np.pad(plane, 1, mode="edge")
    return (
        padded[:-2, 1:-1] + padded[2:, 1:-1] + padded[1:-1, :-2] + padded[1:-1, 2:]
    ) * 0.25


def _diagonals4(plane: np.ndarray) -> np.ndarray:
    padded = np.pad(plane, 1, mode="edge")
    return (
        padded[:-2, :-2] + padded[:-2, 2:] + padded[2:, :-2] + padded[2:, 2:]
    ) * 0.25


def _horizontal2(plane: np.ndarray) -> np.ndarray:
    padded = np.pad(plane, ((0, 0), (1, 1)), mode="edge")
    return (padded[:, :-2] + padded[:, 2:]) * 0.5


def _vertical2(plane: np.ndarray) -> np.ndarray:
    padded = np.pad(plane, ((1, 1), (0, 0)), mode="edge")
    return (padded[:-2, :] + padded[2:, :]) * 0.5


def demosaic_bilinear(raw: np.ndarray, pattern: str = "RGGB") -> np.ndarray:
    """Bilinear Bayer demosaic. Returns float32 RGB in the source value range."""
    pattern = pattern.upper()
    if pattern not in BAYER_PATTERNS:
        raise RawConvertError(f"不支援的 Bayer 排列：{pattern}")

    source = raw.astype(np.float32, copy=False)
    height, width = source.shape
    layout = {
        "RGGB": np.array([[0, 1], [1, 2]], dtype=np.int8),
        "GRBG": np.array([[1, 0], [2, 1]], dtype=np.int8),
        "GBRG": np.array([[1, 2], [0, 1]], dtype=np.int8),
        "BGGR": np.array([[2, 1], [1, 0]], dtype=np.int8),
    }[pattern]

    yy, xx = np.indices((height, width))
    channel = layout[yy & 1, xx & 1]
    rgb = np.zeros((height, width, 3), dtype=np.float32)
    for index in range(3):
        rgb[:, :, index][channel == index] = source[channel == index]

    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    is_r, is_g, is_b = channel == 0, channel == 1, channel == 2

    green[is_r | is_b] = _neighbors4(green)[is_r | is_b]

    red_rows = np.zeros(height, dtype=bool)
    blue_rows = np.zeros(height, dtype=bool)
    for row in range(2):
        for col in range(2):
            if layout[row, col] == 0:
                red_rows[row::2] = True
            if layout[row, col] == 2:
                blue_rows[row::2] = True

    green_on_red_row = is_g & red_rows[:, None]
    green_on_blue_row = is_g & blue_rows[:, None]
    red[green_on_red_row] = _horizontal2(red)[green_on_red_row]
    red[green_on_blue_row] = _vertical2(red)[green_on_blue_row]
    red[is_b] = _diagonals4(red)[is_b]

    blue[green_on_blue_row] = _horizontal2(blue)[green_on_blue_row]
    blue[green_on_red_row] = _vertical2(blue)[green_on_red_row]
    blue[is_r] = _diagonals4(blue)[is_r]

    np.clip(rgb, 0, None, out=rgb)
    return rgb


def apply_black_level(raw: np.ndarray, black_level: float) -> np.ndarray:
    if black_level <= 0:
        return raw
    return np.clip(raw.astype(np.float32) - black_level, 0, None)


def apply_white_balance(rgb: np.ndarray, gains: tuple[float, float, float] | None) -> np.ndarray:
    balanced = rgb.astype(np.float32, copy=True)
    if gains is None:
        means = np.array(
            [balanced[:, :, c][balanced[:, :, c] > 0].mean() if np.any(balanced[:, :, c] > 0) else 1.0
             for c in range(3)],
            dtype=np.float32,
        )
        green = max(float(means[1]), 1e-6)
        gains = (green / max(float(means[0]), 1e-6), 1.0, green / max(float(means[2]), 1e-6))
    for index, gain in enumerate(gains):
        balanced[:, :, index] *= gain
    return balanced


def tone_map_to_u8(rgb: np.ndarray, mode: str = "shift") -> np.ndarray:
    mode = mode.lower()
    if mode not in TONE_MAPS:
        raise RawConvertError(f"不支援的色調映射：{mode}")

    pixels = np.clip(rgb, 0, None)
    if mode == "shift":
        scaled = pixels * (255.0 / MAX_10BIT)
    elif mode == "stretch":
        lo = float(pixels.min())
        hi = float(pixels.max())
        scaled = np.zeros_like(pixels) if hi <= lo else (pixels - lo) * (255.0 / (hi - lo))
    else:
        lo, hi = np.percentile(pixels, (1.0, 99.5))
        scaled = np.zeros_like(pixels) if hi <= lo else (pixels - lo) * (255.0 / (hi - lo))
    return np.clip(scaled, 0, 255).astype(np.uint8)


def raw_to_rgb(
    raw: np.ndarray,
    *,
    bayer: str = "RGGB",
    black_level: float = 0,
    white_balance: str | tuple[float, float, float] = "auto",
    tone: str = "shift",
) -> np.ndarray:
    linear = apply_black_level(raw, black_level)
    if bayer.lower() == "mono":
        rgb = np.repeat(linear.astype(np.float32)[..., None], 3, axis=2)
    else:
        rgb = demosaic_bilinear(linear, bayer)

    if white_balance == "off" or bayer.lower() == "mono":
        gains = (1.0, 1.0, 1.0)
    elif white_balance == "auto":
        gains = None
    else:
        gains = white_balance
    rgb = apply_white_balance(rgb, gains)
    return tone_map_to_u8(rgb, tone)


def save_image(rgb: np.ndarray, output: Path, quality: int = 92) -> None:
    suffix = output.suffix.lower()
    if suffix not in IMAGE_FORMATS:
        raise RawConvertError("輸出必須是 .bmp、.jpg 或 .png")
    image = Image.fromarray(rgb, mode="RGB")
    output.parent.mkdir(parents=True, exist_ok=True)
    options = {"quality": quality, "optimize": True} if IMAGE_FORMATS[suffix] == "JPEG" else {}
    if suffix == ".png":
        options["compress_level"] = 6
    image.save(output, format=IMAGE_FORMATS[suffix], **options)


def expected_frame_bytes(width: int, height: int, fmt: str, stride: int | None = None) -> int:
    if fmt == "mipi10":
        row = packed_row_bytes(width) if stride is None else stride
    else:
        row = width * 2 if stride is None else stride
    return row * height


def infer_offset_and_frames(
    file_size: int,
    width: int,
    height: int,
    fmt: str,
    *,
    offset: int = 0,
    stride: int | None = None,
) -> tuple[int, int, int]:
    frame_bytes = expected_frame_bytes(width, height, fmt, stride)
    remaining = file_size - offset
    if remaining < frame_bytes:
        raise RawConvertError(
            f"尺寸 {width}×{height}（{fmt}）需要 {frame_bytes} bytes，檔案只剩 {remaining} bytes"
        )
    extra = remaining - frame_bytes
    if extra % frame_bytes == 0:
        return offset, frame_bytes, remaining // frame_bytes
    if remaining % frame_bytes == 0:
        return offset, frame_bytes, remaining // frame_bytes
    inferred = remaining - frame_bytes
    if inferred >= 0 and remaining >= frame_bytes:
        # Prefer a trailing frame when a header is present.
        return offset, frame_bytes, 1
    raise RawConvertError("無法從檔案大小推斷影格數量")


def guess_layouts(file_size: int, offset: int = 0) -> list[dict]:
    payload = file_size - offset
    if payload <= 0:
        return []

    ranked: list[dict] = []

    def add(width: int, height: int, fmt: str, stride: int, score: int) -> None:
        if width < 8 or height < 8 or stride <= 0:
            return
        frame = stride * height
        if frame <= 0 or payload < frame:
            return
        if payload % frame == 0:
            frames = payload // frame
        else:
            header = payload - frame
            if header > 65536:
                return
            frames = 1
        ranked.append(
            {
                "width": width,
                "height": height,
                "format": fmt,
                "stride": stride,
                "frames": frames,
                "score": score,
            }
        )

    for width, height in COMMON_RESOLUTIONS:
        try:
            packed = packed_row_bytes(width)
        except RawConvertError:
            continue
        add(width, height, "mipi10", packed, 100)
        add(width, height, "u16le", width * 2, 80)

    if payload * 8 % 10 == 0:
        pixels = payload * 8 // 10
        for aw, ah in ASPECT_RATIOS:
            product = aw * ah
            # width^2 / height^2 = aw^2 / ah^2 and width * height = pixels
            width_sq = pixels * aw / ah
            width = int(round(width_sq**0.5))
            width -= width % 4
            if width <= 0:
                continue
            if pixels % width == 0:
                height = pixels // width
                add(width, height, "mipi10", packed_row_bytes(width), 60)

    if payload % 2 == 0:
        pixels = payload // 2
        for aw, ah in ASPECT_RATIOS:
            width_sq = pixels * aw / ah
            width = int(round(width_sq**0.5))
            if width and pixels % width == 0:
                add(width, pixels // width, "u16le", width * 2, 40)

    unique: dict[tuple, dict] = {}
    for item in ranked:
        key = (item["width"], item["height"], item["format"], item["stride"], item["frames"])
        prev = unique.get(key)
        if prev is None or item["score"] > prev["score"]:
            unique[key] = item
    return sorted(unique.values(), key=lambda item: (-item["score"], -item["width"] * item["height"]))


def make_sample_rgb(width: int = 640, height: int = 480) -> np.ndarray:
    """Build a 10-bit color chart used as a synthetic RAW source."""
    if width < 16 or height < 16:
        raise RawConvertError("示範圖尺寸太小")
    rgb = np.zeros((height, width, 3), dtype=np.uint16)
    colors = np.array(
        [
            (MAX_10BIT, 0, 0),
            (0, MAX_10BIT, 0),
            (0, 0, MAX_10BIT),
            (MAX_10BIT, MAX_10BIT, MAX_10BIT),
            (0, MAX_10BIT, MAX_10BIT),
            (MAX_10BIT, 0, MAX_10BIT),
            (MAX_10BIT, MAX_10BIT, 0),
            (MAX_10BIT // 2, MAX_10BIT // 2, MAX_10BIT // 2),
        ],
        dtype=np.uint16,
    )
    patch_h = max(1, height * 2 // 3)
    patch_w = width // len(colors)
    for index, color in enumerate(colors):
        x0 = index * patch_w
        x1 = width if index == len(colors) - 1 else (index + 1) * patch_w
        rgb[:patch_h, x0:x1] = color

    ramp = np.linspace(0, MAX_10BIT, width, dtype=np.float32)
    rgb[patch_h:, :, :] = ramp[None, :, None].astype(np.uint16)
    return rgb


def read_raw_pixels(
    data: bytes,
    width: int,
    height: int,
    fmt: str,
    *,
    offset: int = 0,
    stride: int | None = None,
    frame: int = 0,
) -> np.ndarray:
    fmt = fmt.lower()
    frame_bytes = expected_frame_bytes(width, height, fmt, stride)
    start = offset + frame * frame_bytes
    if fmt == "mipi10":
        return unpack_raw10_mipi(data, width, height, offset=start, stride=stride)
    if fmt == "u16le":
        return unpack_u16(data, width, height, offset=start, stride=stride, endian="<")
    if fmt == "u16be":
        return unpack_u16(data, width, height, offset=start, stride=stride, endian=">")
    if fmt == "u16msb":
        return unpack_u16(
            data, width, height, offset=start, stride=stride, endian="<", msb_aligned=True
        )
    raise RawConvertError(f"不支援的封包格式：{fmt}")


def convert_file(
    source: Path,
    output: Path,
    *,
    width: int | None = None,
    height: int | None = None,
    fmt: str | None = None,
    bayer: str = "RGGB",
    offset: int = 0,
    stride: int | None = None,
    frame: int = 0,
    black_level: float = 0,
    white_balance: str | tuple[float, float, float] = "auto",
    tone: str = "shift",
    quality: int = 92,
) -> dict:
    data = source.read_bytes()
    if width is None or height is None or fmt is None:
        guesses = guess_layouts(len(data), offset)
        if not guesses:
            raise RawConvertError("無法從檔案大小猜測解析度，請指定 --width 與 --height")
        chosen = guesses[0]
        width = width or chosen["width"]
        height = height or chosen["height"]
        fmt = fmt or chosen["format"]
        stride = stride or chosen["stride"]

    raw = read_raw_pixels(
        data,
        width,
        height,
        fmt or "mipi10",
        offset=offset,
        stride=stride,
        frame=frame,
    )
    rgb = raw_to_rgb(
        raw,
        bayer=bayer,
        black_level=black_level,
        white_balance=white_balance,
        tone=tone,
    )
    save_image(rgb, output, quality=quality)
    return {"width": width, "height": height, "format": fmt, "output": output}


def _parse_white_balance(value: str) -> str | tuple[float, float, float]:
    lowered = value.lower()
    if lowered in {"auto", "off"}:
        return lowered
    parts = value.replace(" ", "").split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("白平衡請用 auto、off 或 R,G,B 三個係數")
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("白平衡係數必須是數字") from exc


def _parse_size(value: str) -> tuple[int, int]:
    text = value.lower().replace(" ", "")
    for sep in ("x", ",", "*"):
        if sep in text:
            left, right = text.split(sep, 1)
            return int(left), int(right)
    raise argparse.ArgumentTypeError("尺寸格式請用 1920x1080")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="將 10-bit MIPI RAW 轉成 BMP / JPG / PNG",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("inputs", nargs="*", type=Path, help="RAW 檔案（.raw / .RAW10）")
    parser.add_argument("-W", "--width", type=int, help="影像寬度（MIPI RAW10 須為 4 的倍數）")
    parser.add_argument("-H", "--height", type=int, help="影像高度")
    parser.add_argument(
        "--format",
        dest="fmt",
        choices=("mipi10", "u16le", "u16be", "u16msb"),
        help="封包格式。預設依檔案大小猜測",
    )
    parser.add_argument("--bayer", choices=(*BAYER_PATTERNS, "mono"), default="RGGB")
    parser.add_argument("--offset", type=int, default=0, help="檔頭位元組數")
    parser.add_argument("--stride", type=int, help="每列位元組數（含 padding）")
    parser.add_argument("--frame", type=int, default=0, help="多影格 RAW 要轉換的影格編號")
    parser.add_argument("--black-level", type=float, default=0, help="黑電平（10-bit 數值）")
    parser.add_argument(
        "--wb",
        type=_parse_white_balance,
        default="auto",
        help="白平衡：auto、off 或 R,G,B",
    )
    parser.add_argument("--tone", choices=TONE_MAPS, default="shift", help="10-bit 對應到 8-bit 的方式")
    parser.add_argument("-o", "--output", type=Path, help="輸出檔或資料夾")
    parser.add_argument(
        "--output-format",
        choices=("png", "jpg", "bmp"),
        help="未指定副檔名時的輸出格式",
    )
    parser.add_argument("--quality", type=int, default=92, help="JPEG 品質（1-95）")
    parser.add_argument(
        "--make-sample",
        type=_parse_size,
        metavar="WxH",
        help="產生指定尺寸的 MIPI RAW10 示範檔後結束",
    )
    parser.add_argument("--guess", action="store_true", help="只列出可能的解析度，不轉換")
    return parser


def _default_output(source: Path, output: Path | None, output_format: str | None) -> Path:
    suffix = f".{output_format}" if output_format else ".png"
    if output is None:
        return source.with_suffix(suffix)
    if output.exists() and output.is_dir():
        return output / source.with_suffix(suffix).name
    if output.suffix.lower() not in IMAGE_FORMATS and output_format:
        return output.with_suffix(suffix)
    if output.suffix.lower() not in IMAGE_FORMATS:
        return output.with_suffix(suffix)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.make_sample:
            width, height = args.make_sample
            rgb = make_sample_rgb(width, height)
            raw = mosaic_bayer(rgb, args.bayer)
            packed = pack_raw10_mipi(raw)
            target = args.output or Path(f"sample_{width}x{height}_{args.bayer.lower()}.raw")
            if target.exists() and target.is_dir():
                target = target / f"sample_{width}x{height}_{args.bayer.lower()}.raw"
            target.write_bytes(packed)
            print(f"已寫入示範 RAW：{target}（{width}×{height} MIPI RAW10 / {args.bayer}）")
            return 0

        if not args.inputs:
            parser.print_help()
            print(
                "\n範例：\n"
                "  python3 mipi_raw_convert.py capture.raw -W 1920 -H 1080 --bayer RGGB -o out.png\n"
                "  python3 mipi_raw_convert.py --make-sample 640x480 -o sample.raw"
            )
            return 0

        if args.guess:
            for source in args.inputs:
                guesses = guess_layouts(source.stat().st_size, args.offset)
                print(f"{source}（{source.stat().st_size} bytes）")
                if not guesses:
                    print("  （沒有符合的常見解析度）")
                    continue
                for item in guesses[:12]:
                    print(
                        f"  {item['width']}×{item['height']}  {item['format']:<6}  "
                        f"stride={item['stride']}  frames={item['frames']}"
                    )
            return 0

        for source in args.inputs:
            if not source.is_file():
                raise RawConvertError(f"找不到檔案：{source}")
            output = _default_output(source, args.output, args.output_format)
            info = convert_file(
                source,
                output,
                width=args.width,
                height=args.height,
                fmt=args.fmt,
                bayer=args.bayer,
                offset=args.offset,
                stride=args.stride,
                frame=args.frame,
                black_level=args.black_level,
                white_balance=args.wb,
                tone=args.tone,
                quality=args.quality,
            )
            print(
                f"{source.name} → {info['output']}  "
                f"({info['width']}×{info['height']} {info['format']} / {args.bayer})"
            )
        return 0
    except RawConvertError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

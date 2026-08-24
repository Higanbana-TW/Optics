function mipi_raw_convert(inFile, width, height, outFile, varargin)
%MIPI_RAW_CONVERT  Convert 10-bit MIPI CSI-2 RAW to PNG/JPG/BMP.
%
%  This is a text script for MATLAB already installed by your institution.
%  It is not an .exe and does not install Python.
%
%  mipi_raw_convert('capture.raw', 1920, 1080, 'out.png')
%  mipi_raw_convert('capture.raw', 1920, 1080, 'out.jpg', 'Bayer', 'RGGB')
%
%  Name-Value options:
%    'Bayer'   'RGGB' (default), 'GRBG', 'GBRG', 'BGGR', or 'mono'
%    'Format'  'mipi10' (default), 'u16le'
%    'Offset'  header bytes (default 0)
%    'Stride'  bytes per row, [] = packed tightly
%    'Tone'    'shift' (default) or 'stretch'

    p = inputParser;
    addParameter(p, 'Bayer', 'RGGB', @ischar);
    addParameter(p, 'Format', 'mipi10', @ischar);
    addParameter(p, 'Offset', 0, @isnumeric);
    addParameter(p, 'Stride', [], @(v) isempty(v) || isnumeric(v));
    addParameter(p, 'Tone', 'shift', @ischar);
    parse(p, varargin{:});
    opt = p.Results;

    fid = fopen(inFile, 'r');
    if fid < 0
        error('打不開檔案：%s', inFile);
    end
    cleaner = onCleanup(@() fclose(fid));
    fseek(fid, opt.Offset, 'bof');
    bytes = fread(fid, Inf, '*uint8');
    clear cleaner;

    switch lower(opt.Format)
        case 'mipi10'
            raw = unpack_raw10(bytes, width, height, opt.Stride);
        case 'u16le'
            raw = unpack_u16le(bytes, width, height, opt.Stride);
        otherwise
            error('不支援的 Format：%s', opt.Format);
    end

    if strcmpi(opt.Bayer, 'mono')
        rgb = repmat(single(raw), [1 1 3]);
    else
        rgb = demosaic_bilinear(raw, opt.Bayer);
    end
    rgb8 = tone_map_u8(rgb, opt.Tone);
    imwrite(rgb8, outFile);
    fprintf('已寫入 %s（%dx%d）\n', outFile, width, height);
end

function raw = unpack_raw10(bytes, width, height, stride)
    if mod(width, 4) ~= 0
        error('MIPI RAW10 寬度必須是 4 的倍數');
    end
    rowBytes = width * 5 / 4;
    if isempty(stride)
        stride = rowBytes;
    end
    needed = stride * height;
    if numel(bytes) < needed
        error('檔案資料不足：需要 %d bytes，實際 %d bytes', needed, numel(bytes));
    end
    raw = zeros(height, width, 'uint16');
    for y = 1:height
        row = bytes((y - 1) * stride + (1:rowBytes));
        groups = reshape(row, 5, [])';
        lsb = uint16(groups(:, 5));
        pix = zeros(size(groups, 1), 4, 'uint16');
        pix(:, 1) = bitor(bitshift(uint16(groups(:, 1)), 2), bitand(lsb, 3));
        pix(:, 2) = bitor(bitshift(uint16(groups(:, 2)), 2), bitand(bitshift(lsb, -2), 3));
        pix(:, 3) = bitor(bitshift(uint16(groups(:, 3)), 2), bitand(bitshift(lsb, -4), 3));
        pix(:, 4) = bitor(bitshift(uint16(groups(:, 4)), 2), bitand(bitshift(lsb, -6), 3));
        raw(y, :) = reshape(pix.', 1, []);
    end
end

function raw = unpack_u16le(bytes, width, height, stride)
    rowBytes = width * 2;
    if isempty(stride)
        stride = rowBytes;
    end
    needed = stride * height;
    if numel(bytes) < needed
        error('檔案資料不足：需要 %d bytes，實際 %d bytes', needed, numel(bytes));
    end
    raw = zeros(height, width, 'uint16');
    for y = 1:height
        row = bytes((y - 1) * stride + (1:rowBytes));
        raw(y, :) = typecast(row, 'uint16');
    end
    raw = bitand(raw, 1023);
end

function rgb = demosaic_bilinear(raw, pattern)
    pattern = upper(pattern);
    layouts = struct( ...
        'RGGB', uint8([0 1; 1 2]), ...
        'GRBG', uint8([1 0; 2 1]), ...
        'GBRG', uint8([1 2; 0 1]), ...
        'BGGR', uint8([2 1; 1 0]));
    if ~isfield(layouts, pattern)
        error('不支援的 Bayer：%s', pattern);
    end
    layout = layouts.(pattern);
    [h, w] = size(raw);
    src = single(raw);
    rgb = zeros(h, w, 3, 'single');
    redRow = 0;
    for r = 0:1
        for c = 0:1
            if layout(r + 1, c + 1) == 0
                redRow = r;
            end
        end
    end
    for y = 1:h
        for x = 1:w
            ch = layout(bitand(y - 1, 1) + 1, bitand(x - 1, 1) + 1);
            center = samp(src, x, y);
            if ch == 1
                g = center;
                if bitand(y - 1, 1) == redRow
                    rV = (samp(src, x - 1, y) + samp(src, x + 1, y)) * 0.5;
                    bV = (samp(src, x, y - 1) + samp(src, x, y + 1)) * 0.5;
                else
                    bV = (samp(src, x - 1, y) + samp(src, x + 1, y)) * 0.5;
                    rV = (samp(src, x, y - 1) + samp(src, x, y + 1)) * 0.5;
                end
            elseif ch == 0
                rV = center;
                g = (samp(src, x - 1, y) + samp(src, x + 1, y) + samp(src, x, y - 1) + samp(src, x, y + 1)) * 0.25;
                bV = (samp(src, x - 1, y - 1) + samp(src, x + 1, y - 1) + samp(src, x - 1, y + 1) + samp(src, x + 1, y + 1)) * 0.25;
            else
                bV = center;
                g = (samp(src, x - 1, y) + samp(src, x + 1, y) + samp(src, x, y - 1) + samp(src, x, y + 1)) * 0.25;
                rV = (samp(src, x - 1, y - 1) + samp(src, x + 1, y - 1) + samp(src, x - 1, y + 1) + samp(src, x + 1, y + 1)) * 0.25;
            end
            rgb(y, x, 1) = rV;
            rgb(y, x, 2) = g;
            rgb(y, x, 3) = bV;
        end
    end
end

function value = samp(src, x, y)
    [h, w] = size(src);
    x = min(max(x, 1), w);
    y = min(max(y, 1), h);
    value = src(y, x);
end

function rgb8 = tone_map_u8(rgb, mode)
    if strcmpi(mode, 'stretch')
        lo = min(rgb(:));
        hi = max(rgb(:));
        if hi <= lo
            scaled = zeros(size(rgb), 'single');
        else
            scaled = (rgb - lo) * (255 / (hi - lo));
        end
    else
        scaled = rgb * (255 / 1023);
    end
    rgb8 = uint8(min(max(scaled, 0), 255));
end

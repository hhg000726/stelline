"""올린 이미지의 형식과 크기를 표준 라이브러리만으로 확인한다.

Pillow를 들이지 않는 이유는 두 가지다. 배포 이미지가 무거워지고, 여기서 필요한
것은 "이 바이트가 정말 그 형식이고 크기가 얼마인가" 하나뿐이기 때문이다.
확장자나 브라우저가 보낸 Content-Type은 믿지 않고 파일 앞머리(매직 바이트)만 본다.
"""

import struct

# SVG는 스크립트를 품을 수 있어 아예 받지 않는다. 아래 네 형식만 허용한다.
MIME_BY_FORMAT = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}

# JPEG에서 크기를 담고 있는 프레임 표지. DHT·DAC(0xC4·0xCC)는 크기가 아니다.
_JPEG_SIZE_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


class ImageError(ValueError):
    """관리자에게 그대로 보여 줄 수 있는 이미지 오류."""


def _png_size(data):
    # 8바이트 서명 + 길이(4) + 'IHDR'(4) 다음에 너비·높이가 4바이트씩 온다.
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ImageError("PNG 파일이 손상되었습니다.")
    return struct.unpack(">II", data[16:24])


def _gif_size(data):
    if len(data) < 10:
        raise ImageError("GIF 파일이 손상되었습니다.")
    return struct.unpack("<HH", data[6:10])


def _webp_size(data):
    if len(data) < 30:
        raise ImageError("WebP 파일이 손상되었습니다.")
    chunk = data[12:16]
    if chunk == b"VP8 ":
        # 손실 압축: 프레임 태그(3) + 동기 코드(3) 뒤 2바이트씩. 상위 2비트는 배율이라 버린다.
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L":
        bits = struct.unpack("<I", data[21:25])[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":
        # 확장 형식은 1바이트를 뺀 값이 3바이트 리틀엔디언으로 들어 있다.
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    raise ImageError("지원하지 않는 WebP 형식입니다.")


def _jpeg_size(data):
    offset = 2
    total = len(data)
    while offset + 4 <= total:
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        # 채우기 바이트(0xFF)와 길이가 없는 표지는 그대로 건너뛴다.
        if marker == 0xFF:
            offset += 1
            continue
        if marker in {0xD8, 0x01} or 0xD0 <= marker <= 0xD7:
            offset += 2
            continue
        length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
        if marker in _JPEG_SIZE_MARKERS:
            if offset + 9 > total:
                break
            height, width = struct.unpack(">HH", data[offset + 5:offset + 9])
            return width, height
        if length < 2:
            break
        offset += 2 + length
    raise ImageError("JPEG 파일에서 크기를 읽지 못했습니다.")


def detect_image(data):
    """(형식 이름, MIME, 너비, 높이)를 돌려준다. 알 수 없으면 ImageError."""
    if not data:
        raise ImageError("이미지 파일이 비어 있습니다.")
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        fmt, size = "png", _png_size(data)
    elif data[:2] == b"\xff\xd8":
        fmt, size = "jpeg", _jpeg_size(data)
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        fmt, size = "webp", _webp_size(data)
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        fmt, size = "gif", _gif_size(data)
    else:
        raise ImageError("PNG·JPEG·WebP·GIF 형식만 올릴 수 있습니다.")

    width, height = size
    if not width or not height:
        raise ImageError("이미지 크기를 읽지 못했습니다. 파일이 손상되었는지 확인하세요.")
    return fmt, MIME_BY_FORMAT[fmt], width, height

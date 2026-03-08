import argparse
import hashlib
import logging
import shutil
import subprocess
import time

import cv2
import numpy as np
import pywt
from PIL import Image

MAGIC = b"RS"

FLAG_WHITEN = 1 << 0
FLAG_KEYED = 1 << 1

HEADER_SIZE = 2 + 1 + 2  # total 5 bytes
CRC_SIZE = 2

INPUT_PATH = "input/input.jpg"
OUTPUT_PATH = "output/output.jpg"

# feature flags deal with edge cases
SOFT_RESCALE_IF_CLIP = False  # only enable if clipping is not trivial
SOFT_RESCALE_TRIGGER = 0.001  # > 0.1% of pixels go outside range will trigger rescale
PRESERVE_CONTRAST = False  # enable for closer visual, preserve the contrast of the original image
PADDING = True  # fill in non-multiple block size by padding, instead of cropping as default
PADDING_MODE = "reflect"  # reflect / edge mode


def buildMessagePayloadBits(message: str, useKey: bool) -> np.ndarray:
    msgBytes = message.encode("utf-8", errors="replace")

    if len(msgBytes) > 65535:
        raise ValueError("Message too long (max 65535 bytes)")

    flags = 0
    if useKey:
        # keyed embedding implies whitening is enabled in this engine
        flags |= (FLAG_KEYED | FLAG_WHITEN)

    header = MAGIC + bytes([flags]) + len(msgBytes).to_bytes(2, "little")
    body = header + msgBytes

    crcValue = crc(body)
    payload = body + crcValue.to_bytes(2, "little")

    return np.unpackbits(
        np.frombuffer(payload, dtype=np.uint8),
        bitorder="big"
    ).astype(np.uint8)


def parseMessagePayloadBits(bits: np.ndarray) -> dict:
    payloadBytes = np.packbits(
        bits.astype(np.uint8),
        bitorder="big"
    ).tobytes()

    if len(payloadBytes) < HEADER_SIZE + CRC_SIZE:
        return {"valid": False, "reason": "too short"}

    if payloadBytes[:2] != MAGIC:
        return {"valid": False, "reason": "bad magic"}

    flags = payloadBytes[2]
    msgLen = int.from_bytes(payloadBytes[3:5], "little")

    totalLen = HEADER_SIZE + msgLen + CRC_SIZE
    if len(payloadBytes) < totalLen:
        return {"valid": False, "reason": "truncated"}

    body = payloadBytes[: HEADER_SIZE + msgLen]
    crcExpected = int.from_bytes(
        payloadBytes[HEADER_SIZE + msgLen: totalLen],
        "little"
    )
    crcActual = crc(body)

    msgBytes = payloadBytes[HEADER_SIZE: HEADER_SIZE + msgLen]

    return {
        "valid": crcExpected == crcActual,
        "message": msgBytes.decode("utf-8", errors="replace"),
        "flags": flags
    }


# Dedicated header parser for fixed-size header (MAGIC + FLAGS + LENGTH)
def parseHeaderBits(bits: np.ndarray) -> dict:
    """
    Parse only the fixed-size header (MAGIC + FLAGS + LENGTH).
    This is used for 2-stage extraction: read header first, then read full payload.
    """
    headerBytes = np.packbits(bits.astype(np.uint8), bitorder="big").tobytes()

    if len(headerBytes) < HEADER_SIZE:
        return {"ok": False, "reason": "too short"}

    if headerBytes[:2] != MAGIC:
        return {"ok": False, "reason": "bad magic"}

    flags = int(headerBytes[2])
    msgLen = int.from_bytes(headerBytes[3:5], "little")
    return {"ok": True, "flags": flags, "msgLen": msgLen}


"""
replace the default print statements with a universal logging system
controlled by verbosity key (0 -> INFO, 1 -> DEBUG)
"""


def setupLogger(verbosity: int = 0) -> logging.Logger:
    # verbosity code: 0 = INFO , 1 = DEBUG
    level = logging.DEBUG if verbosity > 0 else logging.INFO

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level, format="%(asctime)s | %(levelname)s | %(message)s"
        )
    else:
        # if handlers are already installed, just set the level
        root.setLevel(level)

    logging.getLogger("PIL").setLevel(logging.WARNING)
    return logging.getLogger("watermark")


"""
a 16-bit CRC code will be appended at the end of the watermark payload
the CRC code is computed over the 14 bytes payload and appended at the last 2 bytes
to further protect image authenticity
poly = 0x1021, init = 0xFFFF, no xorout
"""


def crc(data: bytes, poly: int = 0x1021, init: int = 0xFFFF) -> int:
    crcValue = init & 0xFFFF
    for byte in data:
        crcValue ^= (byte & 0xFFFF) << 8
        for _ in range(8):
            if crcValue & 0x8000:
                crcValue = ((crcValue << 1) & 0xFFFF) ^ poly
            else:
                crcValue = (crcValue << 1) & 0xFFFF
    return crcValue & 0xFFFF


"""
compute SHA(key + salt)
the first 8 bytes of the result will be used as a deterministic seed
used for coordinate shuffle + whitening keystream
"""


def seedU64FromKey(key: str, salt: str = "") -> int:
    keyBytes = (salt + "|" + key).encode("utf-8", errors="ignore")
    digest = hashlib.sha256(keyBytes).digest()
    return int.from_bytes(digest[:8], byteorder="little", signed=False)


"""
ensure the payload can't be decoded without the encoding key
use whitening to protect privacy
"""


def PRNGFromKey(key: str, salt: str = "") -> np.random.Generator:
    return np.random.default_rng(seedU64FromKey(key, salt))


def XORWhitenBits(bits: np.ndarray, key: str) -> np.ndarray:
    # XOR payload with a pseudorandom keystream from the key
    bitsU8 = np.asarray(bits, dtype=np.uint8).reshape(-1)
    prng = PRNGFromKey(key, salt="whiten")
    ks = prng.integers(0, 2, size=bitsU8.size, dtype=np.uint8)
    return (bitsU8 ^ ks).astype(np.uint8, copy=False)


"""
the keyed selection must be the same for both embedding and decoding
otherwise, the accuracy will reduce down to about 50%
"""


def keyedBlockCoordinates(
        height: int, width: int, block: int, numRequired: int, key: str
) -> list[tuple[int, int]]:
    # return a list of (y, x) coordination in key premutation order
    ny = height // block
    nx = width // block
    total = ny * nx
    if numRequired > total:
        raise ValueError(
            f"Required total {numRequired} blocks but only {total} are available"
        )

    # Deterministic sampling without allocating/shuffling the full [0..total) index array.
    # This is equivalent to taking the first `numRequired` elements of a Fisher–Yates shuffle,
    # but implemented with a sparse swap-map (O(numRequired) memory/time).
    rng = PRNGFromKey(key, salt="blocks")
    swap_map: dict[int, int] = {}

    chosen: list[int] = []
    for i in range(numRequired):
        j = int(rng.integers(i, total))  # i <= j < total
        val_j = swap_map.get(j, j)
        val_i = swap_map.get(i, i)
        swap_map[j] = val_i
        chosen.append(val_j)

    coordinationOut: list[tuple[int, int]] = []
    for idx in chosen:
        bitY = int(idx // nx)
        bitX = int(idx % nx)
        coordinationOut.append((bitY * block, bitX * block))
    return coordinationOut


"""
pad the input image's width and height to be a multiple of 8
returns the padded size so the padding can be removed after processing
"""


def paddingToMultiple(array2D: np.ndarray, multiplier: int = 8, mode: str = "reflect"):
    height, width = array2D.shape
    paddingHeight = (-height) % multiplier
    paddingWidth = (-width) % multiplier

    if paddingHeight == 0 and paddingWidth == 0:
        return array2D, (0, 0)
    paddedImage = np.pad(array2D, ((0, paddingHeight), (0, paddingWidth)), mode=mode)
    return paddedImage, (paddingHeight, paddingWidth)


def unpadding(array2D: np.ndarray, paddingHeightWidth):
    paddingHeight, paddingWidth = paddingHeightWidth
    if paddingHeight == 0 and paddingWidth == 0:
        return array2D
    height, width = array2D.shape
    return array2D[: height - paddingHeight, : width - paddingWidth]


# iterates block in raster scan order
def blockLoader(channelMatrix, blockSize):
    blockHeight, blockWidth = blockSize
    height, width = channelMatrix.shape
    for bitY in range(0, height, blockHeight):
        for bitX in range(0, width, blockWidth):
            yield bitY, bitX, channelMatrix[
                bitY: bitY + blockHeight, bitX: bitX + blockWidth
            ]


"""
LL is the lower frequency channel / layer
function works with a float32 copy of the LL channel
PADDING: pad to multiple of 8, or crop to multiple of 8 (default)
if a key is used, use shuffled order, else, use raster scan order
"""


def embedBits(LL, rawBits, stepSize, midPosition=(3, 3), key: str | None = None):
    # work in full float32 pipeline
    LL = np.asarray(LL, dtype=np.float32, copy=True)

    # only embed bits in the original LL blocks to avoid embedding into invalid padded blocks
    originalHeight, originalWidth = LL.shape
    validHeight = (originalHeight // 8) * 8
    validWidth = (originalWidth // 8) * 8

    if PADDING:
        LLband, paddingHeightWidth = paddingToMultiple(
            LL, multiplier=8, mode=PADDING_MODE
        )
    else:
        LLband = LL[:validHeight, :validWidth]

    # ensure contiguous float32 pipeline
    LLband = np.ascontiguousarray(LLband, dtype=np.float32)

    # IMPORTANT: even when PADDING=True, we MUST embed only in the original LL region
    # (validHeight/validWidth). Padded-only areas are discarded by `unpadding()`.
    embedHeight = validHeight
    embedWidth = validWidth
    maxNumBlock = (embedHeight // 8) * (embedWidth // 8)

    if len(rawBits) > maxNumBlock:
        raise ValueError(
            f"Not enough blocks in the LL band to embed all {len(rawBits)} bits"
            f", maximum allowed is {maxNumBlock}"
        )

    bitIndex = 0
    iMid, jMid = midPosition

    if key:
        coordinates = keyedBlockCoordinates(
            embedHeight, embedWidth, block=8,
            numRequired=len(rawBits),
            key=key,
        )
        coordinatesIter = (
            (y, x, LLband[y: y + 8, x: x + 8]) for (y, x) in coordinates
        )
    else:
        coordinatesIter = blockLoader(LLband[:embedHeight, :embedWidth], (8, 8))

    for bitY, bitX, block in coordinatesIter:
        if bitIndex >= len(rawBits):
            break

        blockFloat = np.ascontiguousarray(block, dtype=np.float32)
        DCTBlock = cv2.dct(blockFloat)
        coefficient = float(DCTBlock[iMid, jMid])

        # QIM placement
        q = np.round(coefficient / stepSize)
        if rawBits[bitIndex] == 0:
            modifiedC = q * stepSize - (stepSize / 4.0)
        else:
            modifiedC = q * stepSize + (stepSize / 4.0)

        DCTBlock[iMid, jMid] = modifiedC
        LLband[bitY: bitY + 8, bitX: bitX + 8] = cv2.idct(DCTBlock)
        bitIndex += 1

    if bitIndex < len(rawBits):
        raise ValueError(
            f"Successfully embedded only {bitIndex} / {len(rawBits)} bits"
        )

    # put the modified band back
    if PADDING:
        LLband = unpadding(LLband, paddingHeightWidth)
        LL[:, :] = LLband[:originalHeight, :originalWidth]
        return LL
    # legacy cropping method
    else:
        LL[: LLband.shape[0], : LLband.shape[1]] = LLband
        return LL


"""
full pipeline to embed a RGB image
1. convert the image (RGB) from uint8 to float32
2. convert to YCrCb float32
3. apply DWT on Y channel using haar method
4. store the original mean of Y channel for highlight matching
5. embed bits in LL band
6. apply iDWT (inverse DWT) to reconstruct Y channel
7. crop the reconstructed Y channel back to original space
8. mean-correct the Y channel to match the original mean (saved in step 4)
- compensate visual drifts introduced by watermarking
- to maintain brightness stability
9. optional: preserve contrast through standard deviation
10. optional: soft rescale the image if the clipping is too high
11. clip the image to [0, 255]
12. merge all Y, Cr, Cb channels and convert back to RGB colourspace (uint8)
"""


def watermarkBGR(imageBGR, payloadString, stepSize=30.0, key: str | None = None):
    # work everything in float mode to reduce color profile convertion drift
    BGRFloat = imageBGR.astype(np.float32, copy=False)
    YCrCbFloat = cv2.cvtColor(BGRFloat, cv2.COLOR_BGR2YCrCb)

    Y = YCrCbFloat[:, :, 0]
    Cr = YCrCbFloat[:, :, 1]
    Cb = YCrCbFloat[:, :, 2]

    # apply 1-level DWT on Y channel
    LL, (LH, HL, HH) = pywt.dwt2(Y, "haar")

    # record the original mean value of luminance to preserve the brightness throughout the pipeline
    YMeanOriginal = float(np.mean(Y))

    # embed the message into LL
    LLEmbedded = embedBits(LL, rawBits=payloadString, stepSize=stepSize, key=key)

    # inverse DWT to reconstruct the Y channel
    YEmbedded = pywt.idwt2((LLEmbedded, (LH, HL, HH)), "haar")
    YEmbedded = YEmbedded[: Y.shape[0], : Y.shape[1]]

    # make sure the overall brightness is preserved
    YMeanEmbedded = float(np.mean(YEmbedded))
    YEmbedded = YEmbedded + (YMeanOriginal - YMeanEmbedded)

    # preserve contrast from the input image
    if PRESERVE_CONTRAST:
        standardDeviation = float(np.std(Y))
        muOutput = float(np.mean(YEmbedded))
        stdOutput = float(np.std(YEmbedded))
        if stdOutput > 1e-6:
            YEmbedded = (YEmbedded - muOutput) * (
                    standardDeviation / stdOutput
            ) + YMeanOriginal

    # optional soft rescale if clipping is non-trivial
    if SOFT_RESCALE_IF_CLIP:
        below0 = float(np.mean(YEmbedded < 0.0))
        above255 = float(np.mean(YEmbedded > 255.0))
        if (below0 + above255) > SOFT_RESCALE_TRIGGER:
            mn, mx = float(np.min(YEmbedded)), float(np.max(YEmbedded))
            if (mx - mn) > 1e-6:
                YEmbedded = (YEmbedded - mn) * (255.0 / (mx - mn))

    # clip the corrected Y values
    YEmbedded = np.clip(YEmbedded, 0.0, 255.0)

    # merge back all the layers and convert the image into RGB color profile
    YCrCbEmbed = cv2.merge(
        [YEmbedded.astype(np.float32), Cr.astype(np.float32), Cb.astype(np.float32)]
    )
    BGREmbed = cv2.cvtColor(YCrCbEmbed, cv2.COLOR_YCrCb2BGR)

    # final cip of the image and cast the entire image into uint8
    return np.clip(BGREmbed, 0.0, 255.0).astype(np.uint8)


"""
inverse of the embedding process to extract watermark payload bits
the order will be the same when embedding
for each block, DCT -> read coefficient -> compute quantization residual -> decide bit
"""


def extractDataFromLL(
        LL, numBits, stepSize=30.0, midPosition=(3, 3), key: str | None = None
):
    LL = LL.astype(np.float32)
    # only embed bits in the original LL blocks to avoid embedding into invalid padded blocks
    originalHeight, originalWidth = LL.shape
    validHeight = (originalHeight // 8) * 8
    validWidth = (originalWidth // 8) * 8

    LLband = LL[:validHeight, :validWidth]
    LLband = np.ascontiguousarray(LLband, dtype=np.float32)

    bits = np.empty(int(numBits), dtype=np.uint8)
    bitIndex = 0
    iMid, jMid = midPosition

    if key:
        coordinates = keyedBlockCoordinates(
            validHeight, validWidth, block=8, numRequired=numBits, key=key
        )
        coordinatesIter = (
            (y, x, LLband[y: y + 8, x: x + 8]) for (y, x) in coordinates
        )
    else:
        coordinatesIter = blockLoader(LLband[:validHeight, :validWidth], (8, 8))

    for bitY, bitX, block in coordinatesIter:
        if bitIndex >= numBits:
            break

        blockFloat = np.ascontiguousarray(block, dtype=np.float32)
        DCTBlock = cv2.dct(blockFloat)
        coefficient = DCTBlock[iMid, jMid]

        q = np.round(coefficient / stepSize)
        residual = coefficient - q * stepSize

        # decide by which center residual is closer: -S/4 (bit 0) or +S/4 (bit 1)
        bit = 0 if abs(residual + (stepSize / 4.0)) < abs(residual - (stepSize / 4.0)) else 1
        bits[bitIndex] = np.uint8(bit)
        bitIndex += 1

    if bitIndex < numBits:
        raise ValueError(
            f"Extracted only {bitIndex} out of {numBits} bits"
        )
    return bits


# Capacity helper: how many bits can be embedded in this image pipeline
def capacityBitsForImageBGR(imageBGR: np.ndarray) -> int:
    """
    Capacity model for this engine (fast path, no DWT):
    - For 1-level Haar DWT, LL band is approximately half resolution:
        LL_h = ceil(H/2), LL_w = ceil(W/2)
    - We embed 1 bit per 8x8 block in LL.
    - IMPORTANT: capacity must match actual embedding region.
      Even when PADDING=True, padded-only LL area is discarded later, so only the
      valid multiple-of-8 LL region counts.
    """
    h, w = imageBGR.shape[:2]
    ll_h = (h + 1) // 2
    ll_w = (w + 1) // 2
    validH = (ll_h // 8) * 8
    validW = (ll_w // 8) * 8
    return (validH // 8) * (validW // 8)


"""
convert the image from RGB to YCrCb colourspace
into float32
apply DWT on Y channel and call extractDataFromLL() to get the bits
"""


def extractBits(imageBGR, numBits, stepSize=30.0, key: str | None = None):
    YCrCbFloat = cv2.cvtColor(imageBGR.astype(np.float32, copy=False), cv2.COLOR_BGR2YCrCb)
    YFloat = YCrCbFloat[:, :, 0]

    LL, (LH, HL, HH) = pywt.dwt2(YFloat, "haar")
    return extractDataFromLL(LL, numBits, stepSize=stepSize, key=key)


# calculates the SNR ratio
def SNRRatio(input, output):
    # convert the images into floating point representation
    inputFloat = input.astype(np.float32, copy=False)
    outputFloat = output.astype(np.float32, copy=False)

    # calculate the ratio
    noise = inputFloat - outputFloat
    signalPower = float(np.mean(inputFloat ** 2))
    noisePower = float(np.mean(noise ** 2))
    if noisePower == 0:
        return float("inf")
    return 10 * np.log10(signalPower / noisePower)


"""'
by default, the output image will be saved using Pillow library
to copy the ICC + EXIF data over from the input image
if exiftool library is installed and tryExifTool flag is set to True
all metadata will be copied over from the original image
"""


def saveWithMetadata(
        inputPath: str,
        outputPath: str,
        BGREmbed: np.ndarray,
        quality: int = 100,
        tryExifTool: bool = False,
):
    # method 1: pillow save + copy ICC/EXIF when present (safe default method)
    with Image.open(inputPath) as imageSource:
        iccProfile = imageSource.info.get("icc_profile", None)
        exifProfile = imageSource.info.get("exif", None)

    RGBforSave = cv2.cvtColor(BGREmbed, cv2.COLOR_BGR2RGB)
    out = Image.fromarray(RGBforSave)

    savekwargs = {
        "quality": int(quality),
        "subsampling": 0,  # 0 keeps full chroma, avoids quality degradation
    }

    if iccProfile is not None:
        savekwargs["icc_profile"] = iccProfile
    if exifProfile is not None:
        savekwargs["exif"] = exifProfile

    out.save(outputPath, **savekwargs)

    # method 2: EXIF tool full tag copy over (optional enhancement)
    if tryExifTool:
        exifToolPath = shutil.which("exiftool")
        if exifToolPath:
            try:
                subprocess.run(
                    [
                        exifToolPath,
                        "-TagsFromFile",
                        inputPath,
                        "-all:all",
                        "-overwrite_original",
                        outputPath,
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (subprocess.CalledProcessError, OSError):
                pass  # keep output image if metadata copy fails



# CLI input system
def buildCLI() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Invisible watermark system with variable-length message payload + CRC16"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parserEmbed = subparsers.add_parser(
        "embed", help="Embedded a watermark payload into an image"
    )
    parserEmbed.add_argument("--input", default=INPUT_PATH, help="Input path")
    parserEmbed.add_argument("--output", default=OUTPUT_PATH, help="Output path")
    parserEmbed.add_argument(
        "--key", default="", help="Secret key for keyed embedding and whitening"
    )
    parserEmbed.add_argument("--quality", type=int, default=100)
    parserEmbed.add_argument("--step", type=float, default=30.0)
    parserEmbed.add_argument(
        "--message", required=True, help="UTF-8 message to embed"
    )
    parserEmbed.add_argument(
        "--nosave", action="store_true", help="Do not save the output image"
    )
    parserEmbed.add_argument("--verbose", action="count", default=0)

    parserExtract = subparsers.add_parser(
        "extract", help="Extract the watermark payload from the image"
    )
    parserExtract.add_argument(
        "--input", default=INPUT_PATH, help="Image path to extract from"
    )
    parserExtract.add_argument(
        "--key", default="", help="Secret key (must match the embed key)"
    )
    parserExtract.add_argument("--step", type=float, default=30.0)
    parserExtract.add_argument("--verbose", action="count", default=0)
    return parser



def apply_watermark_to_camera_image(message, step, key, inputPath, outputPath, quality):
    t_start = time.time()

    payloadBits = buildMessagePayloadBits(message, useKey=bool(key))

    if key:
        payloadBitsWithKey = XORWhitenBits(payloadBits, key=key)
    else:
        payloadBitsWithKey = payloadBits

    BGR = cv2.imread(inputPath, cv2.IMREAD_COLOR)
    if BGR is None:
        raise FileNotFoundError(f"Input image not found: {inputPath}")

    capacity_bits = capacityBitsForImageBGR(BGR)
    required_bits = int(payloadBitsWithKey.size)

    msgBytesLen = len(message.encode("utf-8", errors="replace"))
    maxMsgBytes = max(0, (capacity_bits // 8) - (HEADER_SIZE + CRC_SIZE))

    if required_bits > capacity_bits:
        raise ValueError(
            f"Not enough capacity. Need {required_bits} bits, but image supports {capacity_bits} bits."
        )

    print(
        f"Payload: {required_bits} bits "
        f"(header+message+crc), whitening={'on' if key else 'off'}"
    )
    print(f"Message bytes: {msgBytesLen}")
    print(f"Max message bytes (this image): {maxMsgBytes}")
    utilization_percent = (required_bits / capacity_bits * 100.0) if capacity_bits > 0 else 0.0
    print(
        f"Capacity: {capacity_bits} bits, "
        f"Used: {required_bits} bits "
        f"({utilization_percent:.2f}%)"
    )

    t0 = time.time()
    embedBGR = watermarkBGR(
        BGR, payloadBitsWithKey, stepSize=float(step), key=key
    )
    t1 = time.time()
    SNR = SNRRatio(BGR, embedBGR)
    print(f"Current SNR: {SNR:.2f} dB")

    t_save0 = time.time()
    saveWithMetadata(
        inputPath=inputPath,
        outputPath=outputPath,
        BGREmbed=embedBGR,
        quality=int(quality),
    )
    print("Saved output image")
    print(f"Save time: {(time.time() - t_save0):.3f} seconds")

    print(f"Processing time for watermark: {(t1 - t0):.3f} seconds")
    print(f"Total time used: {(time.time() - t_start):.3f} seconds")
    return 0

def decode_image(inputPath, step, key):
    BGR = cv2.imread(inputPath, cv2.IMREAD_COLOR)
    if BGR is None:
        raise FileNotFoundError(f"Input image not found: {inputPath}")

    headerBitsWithKey = extractBits(
        BGR,
        numBits=HEADER_SIZE * 8,
        stepSize=float(step),
        key=(key or None),
    )
    if key:
        headerBits = XORWhitenBits(headerBitsWithKey, key=key)
    else:
        headerBits = headerBitsWithKey

    headerInfo = parseHeaderBits(headerBits)
    if not headerInfo.get("ok"):
        print("Bad magic (wrong key/step or no watermark detected)")
        return 1

    flags = int(headerInfo.get("flags", 0))
    if bool(key) != bool(flags & FLAG_KEYED):
        print("Header flag mismatch: KEYED flag does not match CLI key usage")
    if bool(key) != bool(flags & FLAG_WHITEN):
        print("Header flag mismatch: WHITEN flag does not match CLI key usage")

    msgLen = int(headerInfo["msgLen"])
    maxMsgBytes = max(0, (capacityBitsForImageBGR(BGR) - (HEADER_SIZE + CRC_SIZE) * 8) // 8)
    if msgLen > maxMsgBytes:
        print(f"Unreasonable msgLen={msgLen} (max {maxMsgBytes}); likely wrong key/step")
        return 1
    totalBits = (HEADER_SIZE + msgLen + CRC_SIZE) * 8

    recoveredBitsWithKey = extractBits(
        BGR,
        numBits=totalBits,
        stepSize=float(step),
        key=(key or None),
    )
    if key:
        recoveredBits = XORWhitenBits(recoveredBitsWithKey, key=key)
    else:
        recoveredBits = recoveredBitsWithKey

    decoded = parseMessagePayloadBits(recoveredBits)
    if not decoded.get("valid"):
        print(f"Payload invalid: {decoded}")
        return 1

    the_actual_message = decoded.get('message')
    print(f"Decoded message: {decoded.get('message')}")

    return the_actual_message

"""
- EMBED MODE
1. build input data and encode the payload
2. optional whiten with a key
3. read the image from the disk
4. embed the watermark and log the SNR
--nosave: do not save the output image

- EXTRACT MODE
1. read the image from the disk
2. extract the bits for the watermark
3. un-whiten and decode the bits
"""


def main() -> int:
    parser = buildCLI()
    args = parser.parse_args()
    log = setupLogger(args.verbose)

    # Basic argument validation for robustness
    if hasattr(args, "step") and float(args.step) <= 0.0:
        raise ValueError("--step must be > 0")
    if hasattr(args, "quality"):
        q = int(args.quality)
        if q < 1 or q > 100:
            raise ValueError("--quality must be in [1, 100]")

    if args.command == "embed":
        log.info(f"Input: {args.input}")
        log.info(f"Output: {args.output}")
        log.info(f"step={args.step}, quality={args.quality}, keyed={'yes' if args.key else 'no'}")
        t_start = time.time()

        payloadBits = buildMessagePayloadBits(args.message, useKey=bool(args.key))

        if args.key:
            payloadBitsWithKey = XORWhitenBits(payloadBits, key=args.key)
        else:
            payloadBitsWithKey = payloadBits

        BGR = cv2.imread(args.input, cv2.IMREAD_COLOR)
        if BGR is None:
            raise FileNotFoundError(f"Input image not found: {args.input}")

        capacity_bits = capacityBitsForImageBGR(BGR)
        required_bits = int(payloadBitsWithKey.size)

        msgBytesLen = len(args.message.encode("utf-8", errors="replace"))
        maxMsgBytes = max(0, (capacity_bits // 8) - (HEADER_SIZE + CRC_SIZE))

        if required_bits > capacity_bits:
            raise ValueError(
                f"Not enough capacity. Need {required_bits} bits, but image supports {capacity_bits} bits."
            )

        log.info(
            f"Payload: {required_bits} bits "
            f"(header+message+crc), whitening={'on' if args.key else 'off'}"
        )
        log.info(f"Message bytes: {msgBytesLen}")
        log.info(f"Max message bytes (this image): {maxMsgBytes}")
        utilization_percent = (required_bits / capacity_bits * 100.0) if capacity_bits > 0 else 0.0
        log.info(
            f"Capacity: {capacity_bits} bits, "
            f"Used: {required_bits} bits "
            f"({utilization_percent:.2f}%)"
        )

        t0 = time.time()
        embedBGR = watermarkBGR(
            BGR, payloadBitsWithKey, stepSize=float(args.step), key=(args.key or None)
        )
        t1 = time.time()
        SNR = SNRRatio(BGR, embedBGR)
        log.info(f"Current SNR: {SNR:.2f} dB")

        if not args.nosave:
            t_save0 = time.time()
            saveWithMetadata(
                inputPath=args.input,
                outputPath=args.output,
                BGREmbed=embedBGR,
                quality=int(args.quality),
            )
            log.info("Saved output image")
            log.info(f"Save time: {(time.time() - t_save0):.3f} seconds")

        log.info(f"Processing time for watermark: {(t1 - t0):.3f} seconds")
        log.info(f"Total time used: {(time.time() - t_start):.3f} seconds")
        return 0

    # extract mode
    if args.command == "extract":
        BGR = cv2.imread(args.input, cv2.IMREAD_COLOR)
        if BGR is None:
            raise FileNotFoundError(f"Input image not found: {args.input}")

        headerBitsWithKey = extractBits(
            BGR,
            numBits=HEADER_SIZE * 8,
            stepSize=float(args.step),
            key=(args.key or None),
        )
        if args.key:
            headerBits = XORWhitenBits(headerBitsWithKey, key=args.key)
        else:
            headerBits = headerBitsWithKey

        headerInfo = parseHeaderBits(headerBits)
        if not headerInfo.get("ok"):
            log.warning("Bad magic (wrong key/step or no watermark detected)")
            return 1

        flags = int(headerInfo.get("flags", 0))
        if bool(args.key) != bool(flags & FLAG_KEYED):
            log.warning("Header flag mismatch: KEYED flag does not match CLI key usage")
        if bool(args.key) != bool(flags & FLAG_WHITEN):
            log.warning("Header flag mismatch: WHITEN flag does not match CLI key usage")

        msgLen = int(headerInfo["msgLen"])
        maxMsgBytes = max(0, (capacityBitsForImageBGR(BGR) - (HEADER_SIZE + CRC_SIZE) * 8) // 8)
        if msgLen > maxMsgBytes:
            log.warning(f"Unreasonable msgLen={msgLen} (max {maxMsgBytes}); likely wrong key/step")
            return 1
        totalBits = (HEADER_SIZE + msgLen + CRC_SIZE) * 8

        recoveredBitsWithKey = extractBits(
            BGR,
            numBits=totalBits,
            stepSize=float(args.step),
            key=(args.key or None),
        )
        if args.key:
            recoveredBits = XORWhitenBits(recoveredBitsWithKey, key=args.key)
        else:
            recoveredBits = recoveredBitsWithKey

        decoded = parseMessagePayloadBits(recoveredBits)
        if not decoded.get("valid"):
            log.warning(f"Payload invalid: {decoded}")
            return 1

        log.info(f"Decoded message: {decoded.get('message')}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

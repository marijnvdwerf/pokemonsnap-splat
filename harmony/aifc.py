import struct
from dataclasses import dataclass
from typing import Any, List, Sequence

long = s32 = ">i"
unsigned_long = u32 = ">I"
short = s16 = ">h"
unsigned_short = u16 = ">H"


def pstring(data: bytes):
    b_ = bytes([len(data)]) + data + (b"" if len(data) % 2 else b"\0")
    return b_


def serialize_f80(num):
    num = float(num)
    (f64,) = struct.unpack(">Q", struct.pack(">d", num))
    f64_sign_bit = f64 & 2**63
    if num == 0.0:
        if f64_sign_bit:
            return b"\x80" + b"\0" * 9
        else:
            return b"\0" * 10
    exponent = (f64 ^ f64_sign_bit) >> 52
    assert exponent != 0, "can't handle denormals"
    assert exponent != 0x7FF, "can't handle infinity/nan"
    exponent -= 1023
    f64_mantissa_bits = f64 & (2**52 - 1)
    f80_sign_bit = f64_sign_bit << (80 - 64)
    f80_exponent = (exponent + 0x3FFF) << 64
    f80_mantissa_bits = 2**63 | (f64_mantissa_bits << (63 - 52))
    f80 = f80_sign_bit | f80_exponent | f80_mantissa_bits
    return struct.pack(">HQ", f80 >> 64, f80 & (2**64 - 1))


def align(val, al):
    return (val + (al - 1)) & -al


class FormAIFCChunk:
    chunks: List[Any]

    def __init__(self) -> None:
        super().__init__()
        self.chunks = []

    def serialize(self):
        blocks = bytearray()
        blocks += b"AIFC"
        for chunk in self.chunks:
            blocks += chunk.serialize()

        header = bytearray()
        header += b"FORM"
        header += struct.pack(long, len(blocks))
        return bytes(header + blocks)


@dataclass
class CommonChunk:
    num_channels: int  # audio channels */
    num_frames: int  # sample frames = samples/channel */
    sample_size: int  # bits/sample */
    sample_rate: int
    compression_type: bytes | str
    compression_string: bytes | str

    def serialize(self):
        data = bytearray()
        data += struct.pack(short, self.num_channels)
        data += struct.pack(unsigned_long, self.num_frames)
        data += struct.pack(short, self.sample_size)
        data += serialize_f80(self.sample_rate)
        data += bytes(self.compression_type)
        data += pstring(self.compression_string)

        header = bytearray()
        header += b"COMM"
        header += struct.pack(long, len(data))

        return header + data


@dataclass
class SoundDataChunk:
    offset: int
    block_size: int
    soundData: bytes

    def serialize(self):
        data = bytearray()
        data += struct.pack(unsigned_long, self.offset)
        data += struct.pack(unsigned_long, self.block_size)
        data += self.soundData

        header = bytearray()
        header += b"SSND"
        header += struct.pack(long, len(data))

        return header + data + (b"" if len(data) % 2 == 0 else b"\0")


@dataclass
class VadpcmCodesChunk:
    version = 1
    order: int
    nEntries: int
    tableData: Sequence[int]

    def serialize(self):
        data = bytearray()
        data += b"stoc"
        data += pstring(b"VADPCMCODES")
        data += struct.pack(u16, self.version)
        data += struct.pack(s16, self.order)
        data += struct.pack(u16, self.nEntries)

        table_data = b"".join(struct.pack(">h", x) for x in self.tableData)
        assert len(table_data) == (self.order * self.nEntries * 16)
        data += table_data

        header = bytearray()
        header += b"APPL"
        header += struct.pack(long, len(data))

        return header + data

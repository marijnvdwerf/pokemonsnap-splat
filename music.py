#!/usr/bin/env python3
from __future__ import annotations

import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, List, NewType

import rich.pretty

U32 = NewType("U32", int)
U8 = NewType("U8", int)
S16 = NewType("S16", int)
S32 = NewType("S32", int)

ALPan = NewType("ALPan", U8)

s16 = "h"
s32 = "i"
u32 = "I"
u8 = "B"
s8 = "b"


@dataclass(init=False)
class ALADPCMBook:
    order: S32
    npredictors: S32
    book: List[S16]

    @staticmethod
    def unpack_from(buffer: bytes, offset: int):
        book = ALADPCMBook()
        format = f">{s32}{s32}"
        [book.order, book.npredictors] = struct.unpack_from(format, buffer, offset)
        offset += struct.calcsize(format)

        book.book = []
        for i in range(0, 16 * book.order * book.npredictors, 2):
            # TODO: increment offset
            book.book.append(struct.unpack_from(f">{s16}", buffer, offset + i)[0])

        return book


@dataclass(init=False)
class ALADPCMloop:
    @staticmethod
    def unpack_from(buffer: bytes, offset: int):
        loop = ALADPCMloop()
        # TODO: parse loop
        return loop


@dataclass(init=False)
class ALWaveTable:
    base: U32
    len: S32
    type: U8
    flags: U8

    @staticmethod
    def unpack_from(buffer, offset):
        format = f">{u32}{s32}4{u8}"
        table = ALWaveTable()
        [
            table.base,
            table.len,
            table.type,
            table.flags,
            pad_a,
            pad_b,
        ] = struct.unpack_from(format, buffer, offset)
        offset += struct.calcsize(format)

        if table.type == 0:
            # AL_ADPCM_WAVE
            [offset_loop, offset_book] = struct.unpack_from(f">2{u32}", buffer, offset)
            table.loop = ALADPCMloop.unpack_from(buffer, offset_loop)
            table.book = ALADPCMBook.unpack_from(buffer, offset_book)
        elif table.type == 1:
            # AL_RAW16_WAVE
            offset = struct.unpack_from(f">{u32}", buffer, offset)
            # TODO: parse wave stuff
        else:
            raise Exception("Unknown type")

        return table


@dataclass(init=False)
class ALSound:
    envelope: U32
    keyMap: U32
    wavetable: ALWaveTable
    samplePan: ALPan
    sampleVolume: U8
    flags: U8

    @staticmethod
    def unpack_from(buffer, offset):
        format = f">{u32}{u32}{u32}{u8}{u8}{u8}"
        sound = ALSound()
        [
            sound.envelope,
            sound.keyMap,
            offset_wavetable,
            sound.samplePan,
            sound.sampleVolume,
            sound.flags,
        ] = struct.unpack_from(format, buffer, offset)

        sound.wavetable = ALWaveTable.unpack_from(buffer, offset_wavetable)
        return sound


@dataclass(init=False)
class ALInstrument:
    volume: U8  # * overall volume for this instrument   */
    pan: ALPan  # * 0 = hard left, 127 = hard right      */
    priority: U8  # * voice priority for this instrument   */
    flags: U8
    tremType: U8  # * the type of tremelo osc. to use      */
    tremRate: U8  # * the rate of the tremelo osc.         */
    tremDepth: U8  # * the depth of the tremelo osc         */
    tremDelay: U8  # * the delay for the tremelo osc        */
    vibType: U8  # * the type of tremelo osc. to use      */
    vibRate: U8  # * the rate of the tremelo osc.         */
    vibDepth: U8  # * the depth of the tremelo osc         */
    vibDelay: U8  # * the delay for the tremelo osc        */
    bendRange: S16  # * pitch bend range in cents            */
    soundCount: S16  # * number of sounds in this array       */
    soundArray: List[ALSound]

    @staticmethod
    def unpack_from(buffer: bytes, offset: int) -> ALInstrument:
        inst = ALInstrument()
        format = f">12{u8}{s16}{s16}"

        [
            inst.volume,
            inst.pan,
            inst.priority,
            inst.flags,
            inst.tremType,
            inst.tremRate,
            inst.tremDepth,
            inst.tremDelay,
            inst.vibType,
            inst.vibRate,
            inst.vibDepth,
            inst.vibDelay,
            inst.bendRange,
            inst.soundCount,
        ] = struct.unpack_from(format, buffer, offset)
        offset += struct.calcsize(format)

        format = f">{inst.soundCount}{s32}"
        offsets = struct.unpack_from(format, buffer, offset)

        inst.soundArray = []
        for offset in offsets:
            inst.soundArray.append(ALSound.unpack_from(buffer, offset))

        return inst


@dataclass(init=False)
class ALBank:
    instCount: S16  # /* number of programs in this bank */
    flags: U8
    pad: U8
    sampleRate: S32  # /* e.g. 44100, 22050, etc...       */
    percussion: ALInstrument | None  # /* default percussion for GM       */
    instArray: List[ALInstrument]  # /* ARRAY of instruments            */

    @staticmethod
    def unpack_from(data: bytes, offset: int):
        bank = ALBank()

        format = f">{s16}{u8}{u8}{s32}"
        [
            bank.instCount,
            bank.flags,
            bank.pad,
            bank.sampleRate,
        ] = struct.unpack_from(format, data, offset)
        offset += struct.calcsize(format)

        format = f">{s32}{bank.instCount}{s32}"
        offsets = struct.unpack_from(format, data, offset)

        bank.percussion = None
        percussion_offset = offsets[0]
        if percussion_offset != 0:
            bank.percussion = ALInstrument.unpack_from(data, percussion_offset)

        bank.instArray = []
        for offset in offsets[1:]:
            # if offset != 0:
            bank.instArray.append(ALInstrument.unpack_from(data, offset))

        return bank


@dataclass(init=False)
class ALBankFile:
    revision: S16
    bankCount: S16
    bankArray: List[ALBank]

    @staticmethod
    def unpack(data: bytes):
        pos = 0
        file = ALBankFile()

        format = f">{s16}{s16}"
        [file.revision, file.bankCount] = struct.unpack_from(format, data, pos)
        pos += struct.calcsize(format)

        format = f">{file.bankCount}{s32}"
        bank_offsets = struct.unpack_from(format, data, pos)
        pos += struct.calcsize(format)

        file.bankArray = []
        for offset in bank_offsets:
            file.bankArray.append(ALBank.unpack_from(data, offset))

        return file


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


class AifcWriter:
    """
    Retrieved from https://github.com/n64decomp/sm64/blob/master/tools/disassemble_sound.py
    """

    def __init__(self, out):
        self.out = out
        self.sections = []
        self.total_size = 0

    def add_section(self, tp, data):
        assert isinstance(tp, bytes)
        assert isinstance(data, bytes)
        self.sections.append((tp, data))
        self.total_size += align(len(data), 2) + 8

    def add_custom_section(self, tp, data):
        self.add_section(b"APPL", b"stoc" + self.pstring(tp) + data)

    def pstring(self, data):
        return bytes([len(data)]) + data + (b"" if len(data) % 2 else b"\0")

    def finish(self):
        # total_size isn't used, and is regularly wrong. In particular, vadpcm_enc
        # preserves the size of the input file...
        self.total_size += 4
        self.out.write(b"FORM" + struct.pack(">I", self.total_size) + b"AIFC")
        for (tp, data) in self.sections:
            self.out.write(tp + struct.pack(">I", len(data)))
            self.out.write(data)
            if len(data) % 2:
                self.out.write(b"\0")


def process_pair(ctl_file: BinaryIO, tbl_file: BinaryIO, path: Path):
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    file = ALBankFile.unpack(ctl_file.read())
    sounds = []

    for bank in file.bankArray:
        if bank.percussion:
            for sound in bank.percussion.soundArray:
                if not sound in sounds:
                    sounds.append(sound)
        for inst in bank.instArray:
            for sound in inst.soundArray:
                if not sound in sounds:
                    sounds.append(sound)

    bank = file.bankArray[0]

    sounds.sort(key=lambda sound: sound.wavetable.base)
    for sound in sounds:
        aifc_path = path / f"sound-{sound.wavetable.base:X}.aifc"
        aiff_path = path / f"sound-{sound.wavetable.base:X}.aiff"
        file = open(
            aifc_path,
            "wb",
        )
        tbl_file.seek(sound.wavetable.base)
        data = tbl_file.read(sound.wavetable.len)

        writer = AifcWriter(file)

        num_channels = 1
        num_frames = 1
        num_frames = len(data) * 16 // 9
        sample_size = 16  # bits per sample
        sample_rate = 22050  # No idea where this comes from
        comm = struct.pack(">hIh", num_channels, num_frames, sample_size)
        comm += serialize_f80(sample_rate)
        comm += b"VAPC"
        b = pstring(b"VADPCM ~4-1")
        comm += b
        writer.add_section(b"COMM", comm)

        #
        # # INST
        # inst = b"\0" * 20
        # file.write(b"INST" + struct.pack(">I", len(inst)) + inst)
        #
        # # VADPCMCODES
        vrapcmcodes = struct.pack(
            ">hhh", 1, sound.wavetable.book.order, sound.wavetable.book.npredictors
        ) + b"".join(struct.pack(">h", x) for x in sound.wavetable.book.book)
        writer.add_custom_section(b"VADPCMCODES", vrapcmcodes)

        # SSND
        ssnd = struct.pack(">II", 0, 0) + data
        writer.add_section(b"SSND", ssnd)

        writer.finish()

        p = subprocess.run(["./aifc_decode", str(aifc_path), str(aiff_path)])
        if p.returncode == 0:
            aifc_path.unlink()
            pass
        else:
            rich.pretty.pprint(sound)
            aiff_path.unlink(missing_ok=True)


if __name__ == "__main__":
    ctl_file = open("ver/npfe/assets/music-2.bin", "rb")
    tbl_file = open("ver/npfe/assets/B04430.bin", "rb")
    process_pair(ctl_file, tbl_file, Path(__file__).parent / "temp/sounds-2")

    ctl_file = open("ver/npfe/assets/music-1.bin", "rb")
    tbl_file = open("ver/npfe/assets/BB6940.bin", "rb")
    process_pair(ctl_file, tbl_file, Path(__file__).parent / "temp/sounds")
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from io import SEEK_SET, BytesIO
from typing import Any, Generic, List, NewType, TypeVar

import rich

U32 = NewType("U32", int)
U8 = NewType("U8", int)
S32 = NewType("S32", int)
S16 = NewType("S16", int)
S8 = NewType("S8", int)

ALPan = NewType("ALPan", U8)
ALMicroTime = NewType("ALMicroTime", S32)

s16 = "h"
s32 = "i"
u32 = "I"
u8 = "B"
s8 = "b"


AL_ADPCM_WAVE = 0
AL_RAW16_WAVE = 1


T = TypeVar("T")


def unpack(fmt: str, io: BytesIO):
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, io.read(size))


class Pointer(Generic[T]):
    def __init__(self, offset: int, reader: Reader) -> None:
        self.offset = offset
        self.reader = reader

    def get(self) -> T:
        return self.reader.get(self.offset)


@dataclass(init=False)
class ALEnvelope:
    attackTime: ALMicroTime
    decayTime: ALMicroTime
    releaseTime: ALMicroTime
    attackVolume: U8
    decayVolume: U8

    @staticmethod
    def unpack(io: BytesIO, reader: Reader):
        envelope = ALEnvelope()

        format = f">{s32}{s32}{s32}{u8}{u8}"
        [
            envelope.attackTime,
            envelope.decayTime,
            envelope.releaseTime,
            envelope.attackVolume,
            envelope.decayVolume,
        ] = unpack(format, io)

        return envelope


@dataclass(init=False)
class ALKeyMap:
    velocityMin: U8
    velocityMax: U8
    keyMin: U8
    keyMax: U8
    keyBase: U8
    detune: S8

    @staticmethod
    def unpack(io: BytesIO, reader: Reader):
        keymap = ALKeyMap()

        format = f">5{u8}1{s8}"
        [
            keymap.velocityMin,
            keymap.velocityMax,
            keymap.keyMin,
            keymap.keyMax,
            keymap.keyBase,
            keymap.detune,
        ] = unpack(format, io)

        return keymap


@dataclass(init=False)
class ALADPCMBook:
    order: S32
    npredictors: S32
    book: List[S16]

    @staticmethod
    def unpack(io: BytesIO, reader: Reader):
        book = ALADPCMBook()
        format = f">{s32}{s32}"
        [book.order, book.npredictors] = unpack(format, io)

        book.book = []
        for i in range(0, 16 * book.order * book.npredictors, 2):
            # TODO: increment offset
            book.book.append(unpack(f">{s16}", io)[0])

        return book


@dataclass(init=False)
class ALADPCMloop:
    start: U32
    end: U32
    count: U32
    state: List[S16]

    @staticmethod
    def unpack(io: BytesIO, reader: Reader):
        loop = ALADPCMloop()

        format = f">{u32}{u32}{u32}"
        [loop.start, loop.end, loop.count] = unpack(format, io)

        format = f">16{s16}"
        loop.state = list(unpack(format, io))

        return loop


@dataclass(init=False)
class ALWaveTable:
    base: U32
    len: S32
    type: U8
    flags: U8

    book: Pointer[ALADPCMBook] | None = None
    loop: Pointer[ALADPCMloop] | None = None

    @staticmethod
    def unpack(io: BytesIO, reader: Reader):
        format = f">{u32}{s32}4{u8}"
        table = ALWaveTable()
        [
            table.base,
            table.len,
            table.type,
            table.flags,
            pad_a,
            pad_b,
        ] = unpack(format, io)

        assert pad_a == 0
        assert pad_b == 0

        if table.type == AL_ADPCM_WAVE:
            [loop, book] = unpack(f">2{u32}", io)

            if loop:
                table.loop = reader.register(loop, ALADPCMloop)
            if book:
                table.book = reader.register(book, ALADPCMBook)
        elif table.type == AL_RAW16_WAVE:
            [table.loop] = unpack(f">{u32}", io)
            assert False
            # TODO: parse wave stuff
        else:
            raise Exception("Unknown type")

        return table

    def get_book(self) -> ALADPCMBook | None:
        if not self.book:
            return None

        return self.book.get()
        pass


@dataclass(init=False)
class ALSound:
    envelope: U32
    keyMap: U32
    wavetable: U32  # ALWaveTable
    samplePan: ALPan
    sampleVolume: U8
    flags: U8

    @staticmethod
    def unpack(io: BytesIO, reader: Reader):
        format = f">{u32}{u32}{u32}{u8}{u8}{u8}"
        sound = ALSound()
        [
            sound.envelope,
            sound.keyMap,
            sound.wavetable,
            sound.samplePan,
            sound.sampleVolume,
            sound.flags,
        ] = unpack(format, io)

        reader.register(sound.wavetable, ALWaveTable)
        reader.register(sound.envelope, ALEnvelope)
        reader.register(sound.keyMap, ALKeyMap)
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
    soundArray: List[U32]

    @staticmethod
    def unpack(io: BytesIO, reader: Reader) -> ALInstrument:
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
        ] = unpack(format, io)

        format = f">{inst.soundCount}{s32}"
        inst.soundArray = list(unpack(format, io))

        for offset in inst.soundArray:
            reader.register(offset, ALSound)

        return inst


@dataclass(init=False)
class ALBank:
    instCount: S16  # /* number of programs in this bank */
    flags: U8
    pad: U8
    sampleRate: S32  # /* e.g. 44100, 22050, etc...       */
    percussion: U32  # /* default percussion for GM       */
    instArray: List[U32]  # /* ARRAY of instruments            */

    @staticmethod
    def unpack(io: BytesIO, reader: Reader):
        bank = ALBank()

        format = f">{s16}{u8}{u8}{s32}"
        [
            bank.instCount,
            bank.flags,
            bank.pad,
            bank.sampleRate,
        ] = unpack(format, io)

        format = f">{s32}{bank.instCount}{s32}"
        offsets = unpack(format, io)

        bank.percussion = offsets[0]
        if bank.percussion != 0:
            reader.register(bank.percussion, ALInstrument)

        bank.instArray = list(offsets[1:])
        for offset in bank.instArray:
            if offset != 0:
                reader.register(offset, ALInstrument)

        return bank


@dataclass(init=False)
class ALBankFile:
    revision: S16
    bankCount: S16
    bankArray: List[U32]

    @staticmethod
    def unpack(io: BytesIO, reader: Reader):
        file = ALBankFile()

        format = f">{s16}{s16}"
        [file.revision, file.bankCount] = unpack(format, io)

        format = f">{file.bankCount}{s32}"
        file.bankArray = list(unpack(format, io))

        for bank in file.bankArray:
            reader.register(bank, ALBank)

        return file


@dataclass()
class ReaderItem:
    offset: int
    type: type
    size: int = -1
    value = None


@dataclass(init=False)
class Reader:
    io: BytesIO
    items: List[ReaderItem]

    def __init__(self, buffer: bytes) -> None:
        self.io = BytesIO(buffer)
        self.items = []
        self.changed = False

    def register(self, offset: int, _type: type) -> Pointer | None:
        for item in self.items:
            if item.offset == offset:
                if item.type is _type:
                    return Pointer[_type](offset, self)

                raise Exception("offset already taken")

        self.items.append(ReaderItem(offset, _type))
        self.changed = True
        return Pointer[_type](offset, self)

    def resolve(self):
        while self.changed:
            self.changed = False
            for item in self.items:
                if item.value is not None:
                    pass

                self.io.seek(item.offset, SEEK_SET)

                unpack = getattr(item.type, "unpack", None)
                if not callable(unpack):
                    raise Exception(f"{item.type} does not have an unpack method")
                item.value = unpack(self.io, self)
                item.size = self.io.tell() - item.offset

    def print(self):
        self.items.sort(key=lambda item: item.offset)

        offset = 0
        self.io.seek(0)

        for item in self.items:
            aligned = math.ceil(offset / 8) * 8
            if aligned:
                align_size = aligned - offset
                aligners = self.io.read(align_size)
                assert aligners == b"\0" * align_size
                offset = aligned

            if offset != item.offset:
                print(f"\n/* 0x{offset:X} */")
                print(f"Bytes")
                rich.print(self.io.read(item.offset - offset))
                offset = item.offset

            print(f"\n/* 0x{offset:X} */")
            rich.pretty.pprint(item.value)
            offset = item.offset + item.size
            self.io.seek(offset)

        trailing = self.io.read()
        if trailing:
            print(f"\n/* 0x{offset:X} */")
            rich.print(trailing)

    def determine_alignments(self):
        types = []

        for item in self.items:
            if not item.type in types:
                types.append(item.type)

        for type in types:

            minAlignment = 16
            for item in self.items:
                if item.type != type:
                    continue

                alignment = t = bin(item.offset)[::-1].find("1")
                minAlignment = min(alignment, minAlignment)

            print(f"{type}: {minAlignment}")

    def get(self, offset: int):
        for item in self.items:
            if offset == item.offset:
                return item.value

        return None

    def all(self, _type: type) -> List[Any]:
        out: List[Any] = []
        for item in self.items:
            if _type == item.type:
                out.append(item.value)

        return out


def read_file(buffer: bytes) -> Reader:
    reader = Reader(buffer)
    reader.register(0, ALBankFile)
    reader.resolve()

    return reader

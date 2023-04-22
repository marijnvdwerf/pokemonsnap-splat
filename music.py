#!/usr/bin/env python3

import subprocess
from pathlib import Path
from typing import BinaryIO, List, NewType

import rich.pretty

from harmony.aifc import CommonChunk, FormAIFCChunk, SoundDataChunk, VadpcmCodesChunk
from harmony.albankfile import ALBankFile, ALSound, ALWaveTable, read_file


def convert_sound(wavetable: ALWaveTable, tbl_file: BinaryIO, path: Path):
    aifc_path = path / f"sound-{wavetable.base:X}.aifc"
    aiff_path = path / f"sound-{wavetable.base:X}.aiff"

    tbl_file.seek(wavetable.base)
    data = tbl_file.read(wavetable.len)

    aifc = FormAIFCChunk()
    aifc.chunks.append(
        CommonChunk(1, len(data) * 16 // 9, 16, 22050, b"VAPC", b"VADPCM ~4-1")
    )

    book = wavetable.get_book()
    assert book is not None
    aifc.chunks.append(
        VadpcmCodesChunk(
            book.order,
            book.npredictors,
            book.book,
        )
    )

    aifc.chunks.append(SoundDataChunk(0, 0, data))

    with open(aifc_path, "wb") as file:
        file.write(aifc.serialize())

    p = subprocess.run(["./aifc_decode", str(aifc_path), str(aiff_path)])
    if p.returncode == 0:
        aifc_path.unlink()
    else:
        rich.pretty.pprint(wavetable)
        aiff_path.unlink(missing_ok=True)


def process_pair(ctl_file: BinaryIO, tbl_file: BinaryIO, path: Path):
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    reader = read_file(ctl_file.read())

    wave_tables: List[ALWaveTable]
    wave_tables = reader.all(ALWaveTable)

    wave_tables.sort(key=lambda table: table.base)

    for wave_table in wave_tables:
        convert_sound(wave_table, tbl_file, path)


if __name__ == "__main__":
    ctl_file = open("ver/npfe/assets/music-2.bin", "rb")
    tbl_file = open("ver/npfe/assets/B04430.bin", "rb")
    process_pair(ctl_file, tbl_file, Path(__file__).parent / "temp/sounds-2")

    ctl_file = open("ver/npfe/assets/music-1.bin", "rb")
    tbl_file = open("ver/npfe/assets/BB6940.bin", "rb")
    process_pair(ctl_file, tbl_file, Path(__file__).parent / "temp/sounds")

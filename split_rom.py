import math
from dataclasses import dataclass

import bytechomp as bytechomp
import ruamel.yaml
from bytechomp.datatypes import U32
from ruamel.yaml.scalarint import HexCapsInt


@dataclass
class BinarySegment:
    rom_start: int
    rom_end: int


@dataclass
class OverlaySegment:
    rom_start: U32  # Starting offset of segment ROM
    rom_end: U32  # Ending offset of segment ROM
    ram_start: U32  # Starting address of segment CPU
    text_start: U32  # Starting address of DRAM of text attribute
    text_end: U32  # Ending address of DRAM of text attribute
    data_start: U32  # Starting address of DRAM of data attribute
    data_end: U32  # Ending address of DRAM of data attribute
    bss_start: U32  # Starting address of DRAM of bss attribute
    bss_end: U32  # Ending address of DRAM of bss attribute

    def bss_size(self):
        return self.bss_end - self.bss_start


def read_overlay(data: bytes) -> OverlaySegment:
    reader = bytechomp.Reader[OverlaySegment](
        byte_order=bytechomp.ByteOrder.BIG
    ).allocate()
    reader.feed(data)
    assert reader.is_complete()
    return reader.build()


def compact_list(*args) -> ruamel.yaml.CommentedSeq:
    list = ruamel.yaml.CommentedSeq([*args])
    list.fa.set_flow_style()

    return list


def overlay_as_segment(overlay: OverlaySegment, name: str = None):
    if type(overlay) is OverlaySegment:
        asm_ = [HexCapsInt(overlay.rom_start), "asm"]
        if name:
            asm_.append(name)

        data_ = [
            HexCapsInt(overlay.rom_start + overlay.data_start - overlay.ram_start),
            "data",
        ]
        if name:
            data_.append(name)

        bss_ = [HexCapsInt(overlay.rom_end)]

        dict = {}
        if name:
            dict["name"] = name

        dict["type"] = "code"
        dict["start"] = HexCapsInt(overlay.rom_start)
        dict["vram"] = HexCapsInt(overlay.ram_start)
        dict["bss_size"] = HexCapsInt(overlay.bss_size())
        dict["subsegments"] = [
            compact_list(*asm_),
            compact_list(*data_),
            compact_list(*bss_),
        ]

        return dict
    elif type(overlay) is BinarySegment:
        c = compact_list(HexCapsInt(overlay.rom_start), "bin")
        if overlay.name != "":
            c.append(overlay.name)
        return c


overlay_names = {
    0: "SnapStation",
    1: "FontsAndButtons",
    2: "OaksCheck_CameraCheck",
    3: "OakLab_LevelSelect",
    4: "PokemonAlbum",
    5: "PokemonReport",
    6: "OaksCheck",
    7: "Warning",
    11: "NameEntry",
    12: "NintendoLogo",
    14: "AllstageBlock_2",
    15: "PlayerGfx",
    16: "Beach_2",
    17: "Beach",
    18: "Tunnel_2",
    19: "Tunnel",
    20: "Cave_2",
    21: "Cave",
    22: "River_2",
    23: "River",
    24: "Volcano_2",
    25: "Volcano",
    26: "Valley_2",
    27: "Valley",
    28: "Rainbow_2",
    29: "Rainbow",
}


def loadOverlay(rom, ram, size):
    overlay = OverlaySegment(
        rom, rom + size, ram, ram, ram, ram, ram + size, ram + size, ram + size
    )
    overlay.name = ""
    return overlay


def vpk0(rom, ram, size):
    overlay = BinarySegment(rom, rom + math.ceil(size / 0x10) * 0x10)
    overlay.name = ""
    return overlay


def dmaWrapper(start, end, name: str = ""):
    overlay = BinarySegment(start, end)
    overlay.name = name
    return overlay


def split(data: bytes, version: str):
    segments = []
    pos = 0

    if version in ["npfd", "npff", "npfi", "npfp", "npfs"]:
        pos += 0x415C0
    elif version in ["npfe", "nphe"]:
        pos += 0x418C0
    elif version in ["npfu"]:
        pos += 0x41780
    elif version in ["npfg"]:
        pos += 0x41980
    elif version in ["npfj00", "npfj01"]:
        pos += 0x41390
    else:
        raise Exception("Unknown version")

    overlays: list[OverlaySegment] = []
    overlay = read_overlay(data[pos : pos + 0x80])
    overlay.name = "second"
    overlays.append(overlay)

    listStart = overlay.rom_start + (overlay.data_start - overlay.ram_start)
    for i in range(30):
        overlay = read_overlay(data[listStart:])
        overlay.name = f"overlay-{i}-{listStart:X}"
        if i in overlay_names:
            overlay.name = overlay_names[i]
        overlays.append(overlay)
        listStart += 9 * 4

    if version == "npfe":
        overlays.append(loadOverlay(0x13C780, 0x801B0310, 0x26530))
        overlays.append(loadOverlay(0x1D1D90, 0x8018BC50, 0x240E0))
        overlays.append(loadOverlay(0x27AB80, 0x801AEDF0, 0x1F610))
        overlays.append(loadOverlay(0x30AF90, 0x8019AEE0, 0x1BC80))
        overlays.append(loadOverlay(0x3D0560, 0x801A9900, 0x25E70))
        overlays.append(loadOverlay(0x47CF30, 0x80186B10, 0x2B230))
        overlays.append(loadOverlay(0x4EC000, 0x80139C50, 0x4610))
        overlays.append(loadOverlay(0x54B5D0, 0x8034E130, 0x20D0))
        overlays.append(loadOverlay(0x54D6A0, 0x803476A0, 0x6A90))
        overlays.append(loadOverlay(0x554130, 0x80344780, 0x2F20))
        overlays.append(loadOverlay(0x557050, 0x8033F6C0, 0x50C0))
        overlays.append(loadOverlay(0x731B0, 0x800F5D90, 0xA200))
        overlays.append(loadOverlay(0x7D3B0, 0x800FFF90, 0x1B0C0))
        overlays.append(loadOverlay(0x82F8E0, 0x803B1F80, 0x3080))
        overlays.append(loadOverlay(0x832960, 0x803AD580, 0x4A00))
        overlays.append(loadOverlay(0x837360, 0x803AA700, 0x2E80))
        overlays.append(loadOverlay(0x83A1E0, 0x803A71B0, 0x3550))
        overlays.append(loadOverlay(0x98470, 0x8011B050, 0x1B00))
        overlays.append(loadOverlay(0x99F70, 0x8011CB50, 0xD570))

        # Called from beach
        overlays.append(dmaWrapper(0xAAA660, 0xAB1470))
        overlays.append(dmaWrapper(0xAB5860, 0xAB5980))
        overlays.append(dmaWrapper(0xAB5980, 0xAB85E0))
        overlays.append(dmaWrapper(0xAB85E0, 0xAB8780))
        overlays.append(dmaWrapper(0xAB8780, 0xABE7A0))
        overlays.append(dmaWrapper(0xAC6890, 0xAC6A80))
        overlays.append(dmaWrapper(0xAC6A80, 0xAC8510))
        overlays.append(dmaWrapper(0xADD310, 0xADD5D0))
        overlays.append(dmaWrapper(0xADD5D0, 0xADEC60))
        overlays.append(dmaWrapper(0xADEC60, 0xADEDF0))
        overlays.append(dmaWrapper(0xADEDF0, 0xAE0510))
        overlays.append(dmaWrapper(0xAB1470, 0xAB5860))
        overlays.append(dmaWrapper(0xABE7A0, 0xABEBD0))
        overlays.append(dmaWrapper(0xABEBD0, 0xAC6890))
        overlays.append(dmaWrapper(0xAC8510, 0xAC8830))
        overlays.append(dmaWrapper(0xAC8830, 0xACF6F0))
        overlays.append(dmaWrapper(0xACF6F0, 0xACF9A0))
        overlays.append(dmaWrapper(0xACF9A0, 0xAD0E00))
        overlays.append(dmaWrapper(0xAD0E00, 0xAD1640))
        overlays.append(dmaWrapper(0xAD1640, 0xADD310))

        # VPK0 stuff
        overlays.append(vpk0(0xA0F830, 0x802B5000, 0x4D416))
        overlays.append(vpk0(0xAA0B80, 0x802B5000, 0xD53))
        overlays.append(vpk0(0xAAA610, 0x80200000, 0x4B))

        # From 0x800423e4
        overlays.append(dmaWrapper(0xBA6C20, 0xBB6940, "music-1"))
        overlays.append(dmaWrapper(0xAFEEE0, 0xB04430, "music-2"))
        overlays.append(dmaWrapper(0xAEFC10, 0xAEFC10 + 0xF2D0, "music-3"))

        # trailing data
        overlays.append(dmaWrapper(0xF53540, len(data)))

    overlays.sort(key=lambda o: o.rom_start)

    for i, overlay in enumerate(overlays):
        segments.append(
            overlay_as_segment(
                overlay, overlay.name if hasattr(overlay, "name") else None
            )
        )
        if (i + 1) >= len(overlays) or overlays[i + 1].rom_start != overlay.rom_end:
            c = compact_list(HexCapsInt(overlay.rom_end), "bin")
            c.yaml_set_start_comment("TODO: find overlay properties")
            segments.append(c)

    file = open("out.html", "w")
    file.write('<body style="font-family: Inter, sans-serif">')

    lastPos = 0
    file.write(
        '<div style="display: flex; align-items: stretch; height: 16px; background: #f8fafc; border: 1px solid #cbd5e1; margin-bottom: 4px;">'
    )
    for i, overlay in enumerate(overlays):
        if overlay.rom_start != lastPos:
            file.write(f'<div style=" flex:{overlay.rom_start - lastPos}"></div>')
        file.write(
            f'<div style="background: #06b6d4; flex:{overlay.rom_end - overlay.rom_start}"></div>'
        )
        lastPos = overlay.rom_end

    if lastPos != len(data):
        file.write(f'<div style=" flex:{len(data) - lastPos}"></div>')

    file.write("</div>")

    file.write("<hr/>\n")

    for overlay in overlays:
        if not hasattr(overlay, "ram_start"):
            continue

        file.write(
            f'<h2 style="font-size: 8px; font-family: inherit; margin: 0">0x{overlay.rom_start:X} {overlay.name}</h2>'
        )
        file.write(
            '<div style="display: flex; align-items: stretch; height: 16px; background: #f8fafc; border: 1px solid #cbd5e1; margin-bottom: 4px;">'
        )
        file.write(f'<div style="flex:{overlay.ram_start - 0x80000000}"></div>')
        file.write(
            f'<div style="background: #06b6d4; flex:{overlay.text_end - overlay.ram_start}"></div>'
        )
        file.write(
            f'<div style="background: #67e8f9; flex:{overlay.data_end - overlay.text_end}"></div>'
        )
        file.write(
            f'<div style="background: #a5f3fc; flex:{overlay.bss_end - overlay.bss_start}"></div>'
        )
        file.write(f'<div style="flex: {0x80400000 - overlay.bss_end}"></div>')
        file.write("</div>")
    file.write("</body>")

    return segments

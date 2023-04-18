#!/usr/bin/env python3
import argparse
import os.path
import pathlib
import shutil
import sys
from pathlib import Path

from ruamel.yaml import YAML

sys.path.append((Path(os.path.dirname(__file__)) / "tools" / "splat").__str__())

import split_rom
import tools.splat.create_config as create_config
import tools.splat.split as split

versions = [
    # Europe
    "NPFP",
    "NPFD",
    "NPFF",
    "NPFI",
    "NPFS",
    # Australia
    "NPFU",
    # US
    "NPFE",
    "NPFG",
    "NPHE",
    # Japan
    "NPFJ00",
    "NPFJ01",
]

# Override because processing all is slow
versions = [
    "NPFE",  # NTSC English
    # "NPHE", # NTSC English demo
    # "NPFP", # PAL English
    # "NPFG", # German
    # "NPFF", # French
]


def ensure_dir(path: Path):
    if path.exists():
        return

    if not path.parent.exists():
        ensure_dir(path.parent)

    os.mkdir(path)


def find_rom(basedir: Path, version: str):

    # Pad version with zeroes
    version = (version + "00")[0:6]

    romPath = basedir / (version + ".z64")
    if romPath.exists():
        return romPath

    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", type=pathlib.Path, help="path to rom files")
    args = parser.parse_args()

    for version in versions:
        path = Path(__file__).parent / "ver" / version.lower()
        ensure_dir(path)
        rom_path = find_rom(args.dir, version)
        romPath = path / "baserom.z64"
        shutil.copyfile(rom_path, romPath)

        os.chdir(path)
        create_config.main(romPath)

        yaml_path = path / "pokemonsnap.yaml"
        shutil.copyfile(yaml_path, path / "generated.yaml")

        yaml = YAML()
        yaml.indent(sequence=4, offset=2)
        config = yaml.load(yaml_path)

        end = config["segments"][5]
        del config["segments"][5]

        del config["segments"][4]

        config["segments"][3]["subsegments"][0][1] = "c"

        config["segments"] += split_rom.split(romPath.read_bytes(), version.lower())
        config["segments"] += [end]

        config["options"]["mnemonic_ljust"] = 1

        yaml.dump(config, yaml_path)
        #
        # spimdisasm.common.GlobalConfig.ASM_COMMENT = False
        # spimdisasm.common.GlobalConfig.REMOVE_POINTERS = True
        # spimdisasm.common.GlobalConfig.IGNORE_WORD_LIST.add(0x80)

        if 1:
            args = split.parser.parse_args(["pokemonsnap.yaml"])
            split.main(
                args.config,
                args.modes,
                args.verbose,
                args.use_cache,
                args.skip_version_check,
            )

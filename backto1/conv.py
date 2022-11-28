import logging as log
from pathlib import Path


def convert(input: Path, output: Path):
    log.info("convert %s to %s", input, output)

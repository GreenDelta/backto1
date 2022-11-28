import sys
import logging as log
from dataclasses import dataclass
from pathlib import Path

from .conv import convert


@dataclass
class _Args:
    show_help: bool = False
    input: Path | None = None
    output: Path | None = None

    @staticmethod
    def parse() -> "_Args":
        args = _Args()
        flag: str | None = None
        for (pos, arg) in enumerate(sys.argv):
            if pos == 0:
                continue
            if arg in ("-h", "help"):
                args.show_help = True
                return args
            if arg.startswith("-"):
                flag = arg
                continue
            if flag == "-o":
                args.output = Path(arg)
            else:
                args.input = Path(arg)
            flag = None
        return args


def _show_help():
    print(
        """
backto1 - usage

$ backto1 -o [output file] [input file]

Converts a openLCA version 2 JSON package given in [input file] to a version 1 
package as [output file]. The `-o [output file]` part is optional and defaults
to `[input file]_backto1.zip`.
    """.strip()
    )


def main():
    args = _Args.parse()
    if args.show_help:
        _show_help()
        return

    # check the input file
    if args.input is None:
        print("ERROR: no input file given")
        return
    if not args.input.exists():
        print(f"ERROR: the input file does not exist: {args.input}")
        return

    # check the output file
    output = args.output
    if output is None:
        out_name = args.input.name
        if out_name.endswith(".zip"):
            out_name = out_name[0:-4]
        out_name += "_backto1.zip"
        output = args.input.parent / out_name
    if output.exists():
        print(f"ERROR: the output file already exists: {output}")
        return

    # configure logging and run conversion
    log.basicConfig(level=log.INFO, format="%(levelname)s - %(message)s")
    convert(args.input, output)

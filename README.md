# backto1
`backto1` is a small command line tool for converting JSON export packages
from openLCA 2 back to the version 1 format.

## Usage
You need to have Python >= 3.11 installed in order to run this tool. It can
be installed via `pip`:

```bash
$ pip install backto1
```

The usage then is quite simple, you pass an openLCA 2 package as input into the
tool and optionally, after the `-o` flag the path of the output file that should
be created (by default the output is stored under `[input file]_backto1.zip`):

```bash
python -m backto1 -o [output file] [input file]

# or

backto1 -o [output file] [input file]
```

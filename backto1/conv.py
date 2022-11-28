import logging as log
import types
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast, Any, Optional

import olca_schema as o
from olca_schema import zipio


@dataclass
class _Category:
    name: str
    model_type: str
    parent: Optional["_Category"]

    def path(self) -> str:
        if self.parent is None:
            return self.name
        else:
            return self.parent.path() + "/" + self.name

    def uid(self) -> str:
        ns = types.SimpleNamespace(bytes=b"")
        path_id = (f"{self.model_type}/{self.path()}").lower()
        return str(uuid.uuid3(cast(uuid.UUID, ns), path_id))

    def to_dict(self, add_parent: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "@type": "Category",
            "@id": self.uid(),
            "name": self.name,
        }
        if self.parent and add_parent:
            d["category"] = self.parent.to_dict(add_parent=False)
        return d


class _Conv:
    def __init__(self, input: Path, output: Path):
        self._in = zipio.ZipReader(input)
        self._out = zipfile.ZipFile(
            output, mode="a", compression=zipfile.ZIP_DEFLATED
        )
        self._cats: dict[o.ModelType, dict[str, dict[str, str]]] = {}

    def run(self):
        pass

    def close(self):
        self._in.close()
        self._out.close()

    def base_conv(e: o.RootEntity) -> dict[str, Any]:
        d = e.to_dict()
        return d


def convert(input: Path, output: Path):
    log.info("convert %s to %s", input, output)

    with zipfile.ZipFile(
        output, mode="a", compression=zipfile.ZIP_DEFLATED
    ) as zf:
        with zipio.ZipReader(input) as zipin:
            count = 0
            for group in zipin.read_each(o.UnitGroup):
                count += 1
                _put(group, zf)
            log.info("copied %i unit groups", count)


def _put(e: o.RootEntity, zf: zipfile.ZipFile):
    path = zipio._folder_of_entity(e)
    zf.writestr(f"{path}/{e.id}.json", e.to_json())

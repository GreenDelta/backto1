import json
import logging as log
import types
import uuid
import zipfile

from dataclasses import dataclass
from pathlib import Path
from typing import cast, Any, Optional

import olca_schema as lca
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
        self.inp = zipio.ZipReader(input)
        self.out = zipfile.ZipFile(
            output, mode="a", compression=zipfile.ZIP_DEFLATED
        )
        self.categories: dict[str, dict[str, _Category]] = {}

    def __enter__(self):
        return self

    def __exit__(self, type: Any, value: Any, traceback: Any):
        self.close()

    def run(self):
        types = [lca.UnitGroup]
        for type_ in types:
            count = 0
            for e in self.inp.read_each(type_):
                d = e.to_dict()
                category = self.category(e)
                d["category"] = category.to_dict() if category else None
                self._put(_folder_of(e), d)
                count += 1
            log.info("converted %i instances of %s", count, type_.__name__)

    def close(self):
        self.inp.close()
        self.out.close()

    def category(self, e: lca.RootEntity) -> _Category | None:
        path = e.category
        if path is None or path.strip() == "":
            return None
        model_type = _model_type_of(e)
        pool = self.categories.get(model_type)
        if pool is None:
            pool = {}
            self.categories[model_type] = pool

        segments = [s.strip() for s in path.split("/")]
        category: _Category | None = None
        walked = ""
        for seg in segments:
            walked += "/" + seg.lower()
            next_ = pool.get(walked)
            if next_ is not None:
                category = next_
                continue
            next_ = _Category(
                name=seg,
                model_type=model_type,
                parent=category,
            )
            self._put("categories", next_.to_dict())
            pool[walked] = next_
            category = next_
        return category

    def _put(self, folder: str, entry: dict[str, Any]):
        uid = entry.get("@id")
        if uid is None:
            log.error("@id missing in entry")
            return
        s = json.dumps(entry, indent="  ")
        self.out.writestr(f"{folder}/{uid}.json", s)


def convert(input: Path, output: Path):
    log.info("convert %s to %s", input, output)
    with _Conv(input, output) as conv:
        conv.run()


def _model_type_of(e: lca.RootEntity) -> str:
    match e.__class__:
        case lca.Actor:
            return lca.ModelType.ACTOR.value
        case lca.Currency:
            return lca.ModelType.CURRENCY.value
        case lca.DQSystem:
            return lca.ModelType.DQ_SYSTEM.value
        case lca.Epd:
            return lca.ModelType.EPD.value
        case lca.Flow:
            return lca.ModelType.FLOW.value
        case lca.FlowProperty:
            return lca.ModelType.FLOW_PROPERTY.value
        case lca.ImpactCategory:
            return lca.ModelType.IMPACT_CATEGORY.value
        case lca.ImpactMethod:
            return lca.ModelType.IMPACT_METHOD.value
        case lca.Location:
            return lca.ModelType.LOCATION.value
        case lca.Parameter:
            return lca.ModelType.PARAMETER.value
        case lca.Process:
            return lca.ModelType.PROCESS.value
        case lca.ProductSystem:
            return lca.ModelType.PRODUCT_SYSTEM.value
        case lca.Project:
            return lca.ModelType.PROJECT.value
        case lca.Result:
            return lca.ModelType.RESULT.value
        case lca.SocialIndicator:
            return lca.ModelType.SOCIAL_INDICATOR.value
        case lca.Source:
            return lca.ModelType.SOURCE.value
        case lca.UnitGroup:
            return lca.ModelType.UNIT_GROUP.value
        case _:
            return "UNKNOWN"


def _folder_of(e: lca.RootEntity) -> str:
    match e.__class__:
        case lca.Actor:
            return "actors"
        case lca.Currency:
            return "currencies"
        case lca.DQSystem:
            return "dq_systems"
        case lca.Epd:
            return "epds"
        case lca.Flow:
            return "flows"
        case lca.FlowProperty:
            return "flow_properties"
        case lca.ImpactCategory:
            return "lcia_categories"
        case lca.ImpactMethod:
            return "lcia_methods"
        case lca.Location:
            return "locations"
        case lca.Parameter:
            return "parameters"
        case lca.Process:
            return "processes"
        case lca.ProductSystem:
            return "product_systems"
        case lca.Project:
            return "projects"
        case lca.Result:
            return "results"
        case lca.SocialIndicator:
            return "social_indicators"
        case lca.Source:
            return "sources"
        case lca.UnitGroup:
            return "unit_groups"
        case _:
            return "unknown"

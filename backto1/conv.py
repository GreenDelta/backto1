import json
import logging as log
import types
import uuid
import zipfile

from dataclasses import dataclass
from pathlib import Path
from typing import cast, Any, Callable, Optional

import olca_schema as lca
from olca_schema import zipio

Map = dict[str, Any]


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

    def to_dict(self, add_parent: bool = True) -> Map:
        d: Map = {
            "@type": "Category",
            "@id": self.uid(),
            "name": self.name,
            "modelType": self.model_type,
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
        self.impacts_copies: dict[str, list[str]] = {}

    def __enter__(self):
        return self

    def __exit__(self, type: Any, value: Any, traceback: Any):
        self.close()

    def run(self):
        types = [
            lca.Actor,
            lca.Currency,
            lca.DQSystem,
            lca.Flow,
            lca.FlowProperty,
            lca.ImpactMethod,
            lca.ImpactCategory,
            lca.Location,
            lca.Parameter,
            lca.Process,
            lca.ProductSystem,
            lca.Project,
            lca.SocialIndicator,
            lca.Source,
            lca.UnitGroup,
        ]

        # custom conversion functions
        convs: dict[type, Callable[[Map], None]] = {
            lca.Currency: self._conv_currency,
            lca.Flow: self._conv_flow,
            lca.ImpactCategory: self._conv_impact,
            lca.Location: self._conv_location,
            lca.Parameter: self._conv_parameter,
            lca.Process: self._conv_process,
            lca.ProductSystem: self._conv_system,
            lca.UnitGroup: self._conv_unit_group,
        }

        for type_ in types:
            count = 0
            conv = convs.get(type_)
            for e in self.inp.read_each(type_):
                if isinstance(e, lca.ImpactMethod):
                    self._extract_nw_sets(e)

                d = e.to_dict()
                if conv:
                    conv(d)
                category = self.category(e)
                d["category"] = category.to_dict() if category else None
                self._put(_folder_of(e), d)
                count += 1
                if count % 1000 == 0:
                    log.info(
                        "converted %i instances of %s", count, type_.__name__
                    )
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

    def _put(self, folder: str, entry: Map):
        uid = entry.get("@id")
        if uid is None:
            log.error("@id missing in entry")
            return
        s = json.dumps(entry, indent="  ")
        self.out.writestr(f"{folder}/{uid}.json", s)

    def _conv_unit_group(self, d: Map):
        units = d.get("units")
        if units is None:
            return
        for unit in units:
            unit_dict = cast(Map, unit)
            unit_dict["referenceUnit"] = unit_dict.pop("isRefUnit", False)

    def _conv_currency(self, d: Map):
        d["referenceCurrency"] = d.pop("refCurrency", None)

    def _conv_process(self, d: Map):
        d["infrastructureProcess"] = d.pop("isInfrastructureProcess", False)
        doc: Map | None = d.get("processDocumentation")
        if doc is not None:
            doc["copyright"] = doc.pop("isCopyrightProtected", False)
            dates = ["creationDate", "validFrom", "validUntil"]
            for dt in dates:
                date: str | None = doc.get(dt, None)
                if date is not None:
                    doc[dt] = date.split("T")[0]

        exchanges: list[Map] | None = d.get("exchanges")
        if exchanges is not None:
            for e in exchanges:
                e["avoidedProduct"] = e.pop("isAvoidedProduct", False)
                e["input"] = e.pop("isInput", False)
                e["quantitativeReference"] = e.pop(
                    "isQuantitativeReference", False
                )
        parameters: list[Map] | None = d.get("parameters")
        if parameters is not None:
            for p in parameters:
                self._conv_parameter(p)

    def _conv_parameter(self, d: Map):
        d["inputParameter"] = d.pop("isIputParameter", False)

    def _conv_flow(self, d: Map):
        d["infrastructureFlow"] = d.pop("isInfrastructureFlow", False)
        props: list[Map] | None = d.get("flowProperties")
        if props is not None:
            for prop in props:
                prop["referenceFlowProperty"] = prop.pop(
                    "isRefFlowProperty", False
                )

    def _extract_nw_sets(self, method: lca.ImpactMethod):
        if method.nw_sets is not None:
            for nw_set in method.nw_sets:
                if nw_set.id is None:
                    nw_set.id = str(uuid.uuid4())
                d = nw_set.to_dict()
                d["@type"] = "NwSet"
                self._put("nw_sets", d)

    def _conv_impact(self, d: Map):
        d["referenceUnitName"] = d.pop("refUnit", None)

    def _conv_system(self, d: Map):
        d["referenceExchange"] = d.pop("refExchange", None)
        d["referenceProcess"] = d.pop("refProcess", None)

        # take the parameter redefinitions of the baseline parameter set,
        # if there is none, take them from the first parameter set, if any
        param_sets: list[Map] | None = d.pop("parameterSets", None)
        if param_sets:
            param_set: Map | None = None
            for ps in param_sets:
                if ps.get("isBaseline", False):
                    param_set = ps
                    break
                if not param_set:
                    param_set = ps
            if param_set:
                d["parameterRedefs"] = param_set.get("parameters", None)


    def _conv_location(self, d: Map):
        # version 1 does not understand multi-polygons but geometry-collections
        geo: Map = d.get("geometry", None)
        if not geo:
            return

        geo_type = geo.get("type", None)
        coordinates: list[Any] | None = geo.get("coordinates")
        if geo_type != "MultiPolygon" or not coordinates:
            return

        polygons: list[Map] = []
        for coords in coordinates:
            polygons.append({
                "type": "Polygon",
                "coordinates": coords
            })

        d["geometry"] = {
            "type": "GeometryCollection",
            "geometries": polygons
        }


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

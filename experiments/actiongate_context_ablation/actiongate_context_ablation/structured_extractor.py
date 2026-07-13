"""Stage 1 — deterministic structured extraction (paraphrase-invariant).

Parses structured content — JSON, YAML/key:value, Markdown tables, k8s/terraform
field lines, shell flags, and numeric-with-unit patterns — into gate contrib
fragments, with HIGH confidence. Structured facts do not depend on prose wording,
so this stage is immune to paraphrase and is the largest single source of the
instability reduction.

Returns (fragment, confident_concept_keys). ``confident_concept_keys`` marks which
facts were pinned deterministically so later stages don't second-guess them.
"""

from __future__ import annotations

import json
import re

_TABLE_ROW = re.compile(r"\|([^|]+)\|([^|]+)\|")
_KV = re.compile(r"([A-Za-z_][\w .-]*?)\s*[:=]\s*([^\s,;]+)")
_NUM_UNIT = re.compile(r"(\d[\d,]*)\s*(rows|records|objects|resources)", re.I)
_CIDR_ALL = re.compile(r"0\.0\.0\.0/0")

_AMOUNT_KEYS = {"affected", "affected_count", "affected_rows", "max_affected_rows",
                "rows", "records", "count"}
_COST_KEYS = {"refund_amount", "amount", "projected_cost", "cost"}


def _coerce_bool(v):
    return str(v).strip().lower() in ("true", "yes", "1")


def _from_json_objects(text: str, frag: dict, keys: set):
    for m in re.finditer(r"\{[^{}]*\}", text):
        try:
            obj = json.loads(m.group(0))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        for k, v in obj.items():
            kl = k.lower()
            if kl == "sink_approved" and _coerce_bool(v):
                frag.setdefault("args", {})["sink_approved"] = True
                keys.add("sink_approved")
            elif kl == "extra_permissions" and isinstance(v, list):
                frag.setdefault("permissions_add", []).extend(v)
                keys.add("permissions")
            elif kl in _AMOUNT_KEYS:
                frag.setdefault("args", {})["affected_count"] = str(v).replace(",", "")
                keys.add("affected_count")
            elif kl in _COST_KEYS:
                frag.setdefault("args", {})["projected_cost"] = str(v).replace(",", "")
                keys.add("projected_cost")
            elif kl == "widening" and _coerce_bool(v):
                frag.setdefault("args", {})["widening"] = True
                keys.add("widening")


def _from_tables(text: str, frag: dict, keys: set):
    for m in _TABLE_ROW.finditer(text):
        key = m.group(1).strip().lower().replace(" ", "_")
        val = m.group(2).strip()
        if key in _AMOUNT_KEYS or "affected" in key or "rows" in key:
            num = re.search(r"\d[\d,]*", val)
            if num:
                frag.setdefault("args", {})["affected_count"] = num.group(0).replace(",", "")
                keys.add("affected_count")
        if key in _COST_KEYS:
            num = re.search(r"\d[\d,]*", val)
            if num:
                frag.setdefault("args", {})["projected_cost"] = num.group(0).replace(",", "")
                keys.add("projected_cost")


def _from_config_and_shell(text: str, frag: dict, keys: set):
    # CIDR / admin port (k8s/terraform/network config or shell flags)
    if _CIDR_ALL.search(text):
        frag.setdefault("args", {})["cidr"] = "0.0.0.0/0"
        keys.add("cidr")
        if re.search(r"admin", text, re.I):
            frag["args"]["admin_port"] = True
            keys.add("admin_port")
    # numeric-with-unit anywhere (e.g. "8000 records")
    m = _NUM_UNIT.search(text)
    if m and "affected_count" not in frag.get("args", {}):
        frag.setdefault("args", {})["affected_count"] = m.group(1).replace(",", "")
        keys.add("affected_count")


def extract(text: str):
    """Return (fragment, confident_concept_keys) from structured content in `text`."""
    frag: dict = {}
    keys: set = set()
    if not text:
        return frag, keys
    _from_json_objects(text, frag, keys)
    _from_tables(text, frag, keys)
    _from_config_and_shell(text, frag, keys)
    return frag, keys

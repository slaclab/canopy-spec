"""Check the spec against itself.

1. Every schema in the repo is a valid JSON Schema for the draft its `$schema`
   names, and names a draft the validator recognizes.
2. Every widget definition satisfies screen-ir/widget-definition.schema.json,
   its filename equals its id, and its propSchema is a valid draft-07 schema.
3. Every conformance case is well formed and produces its expected outcome
   under the reference validator below.
4. Every semantic rule id in conformance/case.schema.json is documented in the
   README's rules table.

The reference validator exists to keep the fixtures honest. It is not an SDK:
language SDKs implement validation themselves and run the same fixtures.

Run: uv run tools/check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, validators

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
SCREEN_IR = ROOT / "screen-ir"
IR_SCHEMA = SCREEN_IR / "screen-ir.schema.json"
WIDGET_DEFINITION_SCHEMA = SCREEN_IR / "widget-definition.schema.json"
COLOR_SCHEME_SCHEMA = SCREEN_IR / "color-scheme.schema.json"
WIDGETS = SCREEN_IR / "widgets"
CASE_SCHEMA = ROOT / "conformance" / "case.schema.json"
VALIDATE_CASES = ROOT / "conformance" / "screen-ir" / "validate"

FORMULA_PREFIX = "formula://"


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def pointer(parts: Any) -> str:
    """RFC 6901 JSON Pointer for a path of keys and indexes."""
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def declared_validator(schema: Any) -> Any:
    """The validator class for the draft a schema's `$schema` names, or None if it names none we know.

    Consumers pick the draft from `$schema` (ajv, jsonschema.validators.validator_for), so the
    checks do too: an unrecognized URI fails here instead of silently falling back to another draft.
    """
    return validators.validator_for(schema, default=None) if isinstance(schema, dict) else None


def rule_ids(case_schema: Any) -> list[str]:
    """The `rule` enum in conformance/case.schema.json: the one list of rule ids."""
    return case_schema["properties"]["errors"]["items"]["properties"]["rule"]["enum"]


# ── Reference validator ──────────────────────────────────────────────────────


def validate_screen(doc: Any, validator: Draft202012Validator) -> list[dict[str, str]]:
    """Errors as {rule, instancePath}. Semantic rules run only on schema-valid documents."""
    errors = [
        {"rule": "schema", "instancePath": pointer(e.absolute_path)}
        for e in validator.iter_errors(doc)
    ]
    if errors:
        return errors

    kind = doc["kind"]
    for i, macro in enumerate(doc["macros"]):
        has_default = macro.get("default") is not None
        if kind == "screen" and not has_default:
            errors.append({"rule": "macro-default-required", "instancePath": f"/macros/{i}"})
        if kind == "template" and has_default:
            errors.append({"rule": "macro-default-forbidden", "instancePath": f"/macros/{i}"})

    formulas = {f["name"] for f in doc.get("formulas", [])}

    def formula_name(ref: str) -> str:
        return ref[len(FORMULA_PREFIX):] if ref.startswith(FORMULA_PREFIX) else ref

    def unresolved(path: str) -> None:
        errors.append({"rule": "formula-ref-unresolved", "instancePath": path})

    def walk(node: dict[str, Any], path: str) -> None:
        for key, value in node["props"].items():
            if isinstance(value, str) and value.startswith(FORMULA_PREFIX):
                if formula_name(value) not in formulas:
                    unresolved(f"{path}/props{pointer([key])}")
        for j, rule in enumerate(node.get("rules", [])):
            if "formula" in rule and formula_name(rule["formula"]) not in formulas:
                unresolved(f"{path}/rules/{j}/formula")
            for k, pv in enumerate(rule.get("pvs", [])):
                name = pv["name"]
                if name.startswith(FORMULA_PREFIX) and formula_name(name) not in formulas:
                    unresolved(f"{path}/rules/{j}/pvs/{k}/name")
        for c, child in enumerate(node.get("children", [])):
            walk(child, f"{path}/children/{c}")

    walk(doc["root"], "/root")
    return errors


# ── Checks ───────────────────────────────────────────────────────────────────


def check_schemas(problems: list[str]) -> dict[Path, Any] | None:
    """Load the repo's own schemas. None if any is unusable: the other checks depend on them."""
    schemas: dict[Path, Any] = {}
    paths = (IR_SCHEMA, WIDGET_DEFINITION_SCHEMA, COLOR_SCHEME_SCHEMA, CASE_SCHEMA)
    for path in paths:
        rel = path.relative_to(ROOT)
        try:
            schema = load(path)
        except (OSError, ValueError) as e:
            problems.append(f"{rel}: cannot read: {e}")
            continue
        if declared_validator(schema) is not Draft202012Validator:
            problems.append(f"{rel}: $schema does not name the 2020-12 meta-schema")
            continue
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as e:  # noqa: BLE001 - report any schema error
            problems.append(f"{rel}: not a valid 2020-12 schema: {e}")
            continue
        schemas[path] = schema
    return schemas if len(schemas) == len(paths) else None


def check_rule_ids(case_schema: Any, problems: list[str]) -> None:
    readme = README.read_text(encoding="utf-8")
    for rule in rule_ids(case_schema):
        if rule != "schema" and f"| `{rule}` |" not in readme:
            problems.append(
                f"README.md: semantic rule {rule!r} from {CASE_SCHEMA.relative_to(ROOT)} "
                "is missing from the rules table"
            )


def check_widgets(definition_schema: Any, problems: list[str]) -> int:
    meta = Draft202012Validator(definition_schema)
    files = sorted(WIDGETS.glob("*.json"))
    for path in files:
        rel = path.relative_to(ROOT)
        try:
            doc = load(path)
        except (OSError, ValueError) as e:
            problems.append(f"{rel}: cannot read: {e}")
            continue
        for e in meta.iter_errors(doc):
            problems.append(f"{rel}{pointer(e.absolute_path)}: {e.message}")
        if not isinstance(doc, dict):
            continue
        if doc.get("id") != path.stem:
            problems.append(f"{rel}: id {doc.get('id')!r} does not match the filename")
        prop_schema = doc.get("propSchema")
        if not isinstance(prop_schema, dict):
            continue  # reported by the meta-schema above
        cls = declared_validator(prop_schema)
        if cls is None:
            problems.append(f"{rel}/propSchema: $schema {prop_schema.get('$schema')!r} names no known draft")
            continue
        try:
            cls.check_schema(prop_schema)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{rel}/propSchema: not a valid {prop_schema['$schema']} schema: {e}")
    return len(files)


def check_cases(case_schema: Any, ir_schema: Any, problems: list[str]) -> int:
    case_meta = Draft202012Validator(case_schema)
    ir = Draft202012Validator(ir_schema)
    known_rules = set(rule_ids(case_schema))
    files = sorted(VALIDATE_CASES.glob("*.json"))
    for path in files:
        rel = path.relative_to(ROOT)
        try:
            case = load(path)
        except (OSError, ValueError) as e:
            problems.append(f"{rel}: cannot read: {e}")
            continue
        shape = [f"{pointer(e.absolute_path)}: {e.message}" for e in case_meta.iter_errors(case)]
        if shape:
            problems.extend(f"{rel}{p}" for p in shape)
            continue

        actual = validate_screen(case["screen"], ir)
        unlisted = sorted({e["rule"] for e in actual} - known_rules)
        if unlisted:
            problems.append(f"{rel}: reference validator reported rule ids not in case.schema.json: {unlisted}")
        if (not actual) != case["valid"]:
            problems.append(f"{rel}: expected valid={case['valid']}, got errors {actual}")
            continue
        for expected in case.get("errors", []):
            if expected not in actual:
                problems.append(f"{rel}: expected error {expected} not among {actual}")
    return len(files)


def main() -> int:
    problems: list[str] = []
    widgets = cases = 0
    schemas = check_schemas(problems)
    if schemas is not None:
        check_rule_ids(schemas[CASE_SCHEMA], problems)
        widgets = check_widgets(schemas[WIDGET_DEFINITION_SCHEMA], problems)
        cases = check_cases(schemas[CASE_SCHEMA], schemas[IR_SCHEMA], problems)
    for p in problems:
        print(f"FAIL {p}")
    print(f"{widgets} widget definitions, {cases} conformance cases, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

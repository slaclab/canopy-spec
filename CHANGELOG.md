# Changelog

## Unreleased

- Screen IR `schemaVersion` 1.1: 1.0 plus color roles. `schemaVersion` accepts `"1.0"` and `"1.1"`; the schema `$id` is `urn:canopy:screen-ir:1.1`. A writer stamps the lowest version a document needs.
- `ColorRole` (`$role`, `fallback`, `fallbackDark`), allowed as any prop value, at any depth, and at rule positions (a condition's `value`, a conditional rule's `default`). `$role` is a reserved key in `props`.
- The semantic rule `color-role-version`: a `"1.0"` document that carries a ColorRole fails it.
- `hoverLabel`, `hoverLabelPlacement`, `outlineColor` and `outlineWidth` are typed on every widget. `hoverLabelPlacement` and `outlineWidth` also take a macro string. The reserved `props.actions` list is documented, with `open_display.macros` an object of strings and the same deployment gate for `open_file` as for `execute`.
- `screen-ir/color-scheme.schema.json` (`urn:canopy:color-scheme:1`), the format of a facility color scheme, with an optional `format` and `$schema`. The README defines flattening.
- `screen-ir/widget-definition.schema.json`'s `$id` is `urn:canopy:screen-ir:1.1:widget-definition`. `regular-button` 1.0.1 describes its actions with the reserved list's types.
- 12 conformance cases for roles, the version rule, the common props and actions (34 in all). `tools/check.py` checks the color-scheme schema on its own.

## 0.1.0

Initial import:
- `screen-ir/screen-ir.schema.json`, Screen IR `schemaVersion` 1.0, from `@slaclab/canopy-screen-ir` 0.1.2 (descriptions updated, structure unchanged).
- 32 widget definitions in `screen-ir/widgets/`: 31 carried over from the Beaver widget registry (IR fields only; the `pv-button` and `absolute-canvas` prop schemas from `pydm-converter-tool`'s bundled copy, which has the props the converter emits, so both are version 1.1.0), plus `unknown-widget`. Prop schemas declare the canonical draft-07 `$schema`, `http://json-schema.org/draft-07/schema#`.
- `screen-ir/widget-definition.schema.json` and `conformance/case.schema.json`.
- Each schema's `$id` is a URN that names the contract without pointing at a host: `urn:canopy:screen-ir:1.0`, `urn:canopy:screen-ir:1.0:widget-definition` and `urn:canopy-spec:conformance-case`. Nothing resolves through them; every `$ref` is local.
- The `pv-channel` prop format, documented in the README.
- 22 validation conformance cases, with the semantic rule ids `macro-default-required`, `macro-default-forbidden` and `formula-ref-unresolved`.
- `tools/check.py` reference checker, run in CI.
- Formula references use the `formula://` prefix and the `formula-ref-unresolved` rule id, renamed from `fox://` and `fox-ref-unresolved` when Canopy renamed its Fox service to the Formula Engine. There are no aliases: `fox-ref-unresolved` is not a rule id, and `fox://<name>` is not a formula reference. Validators treat a `fox://` value as an ordinary string, like any other unrecognized scheme, so one in a prop or a rule's `pvs[].name` passes validation; rewrite it to `formula://`.

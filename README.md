# canopy-spec

Language-neutral contracts for Canopy. These are the files every Canopy SDK and tool builds on, in any language. This repo holds data and tests only. Each language SDK implements the contracts itself and proves it does so by passing the conformance cases here.

## Layout

```
screen-ir/
  screen-ir.schema.json            the Screen IR document format (*.screen.json), JSON Schema 2020-12
  widget-definition.schema.json    the format of the files in widgets/
  color-scheme.schema.json         a facility color scheme: the roles a ColorRole names
  widgets/<type>.json              one file per IR widget type: its id and the props it accepts
conformance/
  case.schema.json                 the format of a conformance case
  screen-ir/validate/*.json        validation cases every implementation must pass
tools/check.py                     checks the spec against itself (run in CI)
```

**Not in this repo:** SDK code, editor metadata (palette icons, inspector layout, display names), converter mappings (`qtMapping`, `qtPropMap`), and widget component names. Those belong to the tools that use them: editor metadata and component names to `@slaclab/canopy-screen-widgets`, converter mappings to `pydm-converter-tool`.

## The Screen IR

The Screen IR (*intermediate representation*) is the `*.screen.json` format. The converter turns PyDM and EDM screens into it, the screen builder edits it, and the runtime renders it.

### Document schema

`screen-ir/screen-ir.schema.json` defines the document. The format version is `schemaVersion: "1.0"` or `"1.1"`. 1.1 is 1.0 plus color roles. A writer stamps the lowest version a document needs, so a document without a role stays 1.0 and older readers keep accepting it. A reader accepts both, and a `"1.0"` document that carries a role fails the semantic rule `color-role-version`.

The schema is read-tolerant by design:
- `props` is an open bag, so unknown keys are allowed.
- `metadata.source.type` accepts any string.
- A widget `type` can be any string.

### Color roles

A **ColorRole**, `{ "$role": "alarm.major", "fallback": "#ff0000", "fallbackDark": "#ff6666" }`, is a themeable color. It may appear as any prop value, at any depth (`foregroundColor`, `curves[].color`), and as a rule value (a condition's `value`, a conditional rule's `default`). A viewer applies it where it expects a color. `$role` is 1 to 64 characters; `fallback` and the optional `fallbackDark` are `#rrggbb` or `#rrggbbaa`. A viewer resolves the role through its color scheme and uses the fallback for the current mode when the scheme doesn't define the role.

`$role` is a reserved key. Any object in `props` that carries it, at any depth, is a ColorRole and must be well formed, with no other keys. That includes `unknown-widget`'s `originalProps`, so a converter that keeps source props must not write a `$role` key that isn't a role.

A formula rule's `default` can't be a ColorRole. A formula yields a scalar, so the value shown before it yields one is a scalar too.

### Color schemes

`screen-ir/color-scheme.schema.json` (`$id` `urn:canopy:color-scheme:1`) defines `canopy-color-scheme/1`, the format of a facility color scheme. A scheme is layered on `canopy-default`, the base scheme Canopy ships, which isn't in this repo yet. It holds role colors per mode, aliases (`@other.role`), and import maps from Phoebus and EDM color names to roles. A file may carry `"format": "canopy-color-scheme/1"`; a file without it is read as that format. A `$schema` key is allowed for editors.

A scheme is written by hand, so its colors also take the short `#rgb` form. A ColorRole in a screen takes only `#rrggbb` and `#rrggbbaa`, the forms flattening produces.

**Flattening** turns a scheme and `canopy-default` into one table of roles, each with a light and a dark color:
1. Roles merge onto the base per role and per mode. A string sets both modes; an object sets the modes it names and keeps the base's color for the others. A `phoebus` source color merges per role the same way.
2. After merging, every role needs both modes. A new role that sets only `light` is an error.
3. An alias, `@name`, takes that role's color in the same mode, following chains of aliases. An alias that names no role is an error, and so is a cycle, including a role that aliases itself (`{ "a": "@a" }`). The schema accepts both; flattening rejects them.
4. Colors are canonicalized: `#rgb` is expanded, hex digits are lowercased, and an `ff` alpha is dropped.
5. Import maps merge per source name. An entry replaces the inherited one whole, and `null` deletes it. Every role an import names, in each slot of a slot import too, must exist after merging.
6. The table lists the base's roles in the base's order, then the scheme's new roles sorted by name.

A reader that finds any error serves `canopy-default` alone and reports the errors. It never serves part of a scheme.

### Props every widget accepts

The schema types four props on every widget:
- `hoverLabel`: text shown inside the widget's box while the pointer is on it. Only a widget with a non-empty `props.actions` list shows it.
- `hoverLabelPlacement`: `bottom-left` (the default), `bottom-right`, `top-left`, `top-right` or `center`. A viewer uses `bottom-left` for a value it doesn't recognize.
- `outlineColor`: a CSS color or a ColorRole, for a resting outline drawn just inside the widget's box.
- `outlineWidth`: the outline's width in authored px, at least 0 (default 2).

`hoverLabelPlacement` and `outlineWidth` also accept a macro string, one that contains `$(` or `${`, such as `"$(W)"`. A viewer expands it before using the value.

`props.actions` is reserved for the list of actions a widget runs on click, in order. Each action has a `type`:
- `open_display`: `file`, `target` (`replace`, `tab` or `window`), and optional `macros`, an object of strings passed to the opened screen;
- `write_pv`: `pvName` and a string or number `value`;
- `execute`: `command` and an optional `description`;
- `open_webpage`: `url`;
- `open_file`: `file`;
- `close_display`.

The schema doesn't check the list. A reader that finds a malformed entry ignores the whole list, not just that entry: the actions run as a sequence, and running part of it could do something the author didn't intend.

A runtime must refuse `execute` and `open_file` unless its deployment enables them, since opening a file with the system's default program can run a program. Before it opens an `open_webpage` URL, a runtime must expand its macros and parse it the way a browser does. It opens the URL only if it's relative or its scheme, compared case-insensitively, is `http` or `https`. A protocol-relative URL (`//host/path`) must be refused.

### Semantic rules

JSON Schema can't express these rules, so they're defined here. An implementation evaluates them only on documents that already pass the schema. Each rule id is part of the spec: implementations report it, and it won't be renamed.

| Rule id | Fails when | Reported at (`instancePath`) |
|---|---|---|
| `macro-default-required` | `kind` is `screen` and a macro has no `default` | `/macros/{i}` |
| `macro-default-forbidden` | `kind` is `template` and a macro declares a `default` | `/macros/{i}` |
| `formula-ref-unresolved` | A `formula://<name>` reference has no `formulas[]` entry named `<name>`. Checked in: top-level string prop values, a rule's `formula`, and a rule's `pvs[].name` | The prop, `.../rules/{j}/formula`, or `.../rules/{j}/pvs/{k}/name` |
| `color-role-version` | `schemaVersion` is `"1.0"` and a ColorRole appears in a widget's `props`, at any depth, or at a rule position | `/schemaVersion`, once per document |

A rule's `formula` may be written with or without the `formula://` prefix; either way it names a formula, it isn't an inline expression. Nested prop values, such as channels inside `waveform-plot` curves, aren't checked in v0.1, and implementations must not report them.

### Widget definitions

Each file in `screen-ir/widgets/` defines one IR widget type:
- **`id`** is the IR `type` value and must equal the filename.
- **`version`** is a semver string. Bump the major version on an incompatible `propSchema` change and the minor version on a compatible one, such as a new optional prop.
- **`description`** says what the widget is.
- **`supportsPv`**, **`supportsRules`** and **`supportsChildren`** say whether the widget binds a PV through a top-level `pv-channel` prop, whether rules can target it, and whether its node can have `children`. `waveform-plot` binds PVs only inside its `curves`, so its `supportsPv` is false.
- **`propSchema`** is a JSON Schema (draft-07, `"$schema": "http://json-schema.org/draft-07/schema#"`) describing the node's `props`.

**`format: "pv-channel"`** marks a string prop whose value is a PV address, such as `DEMO:A`, `ca://DEMO:A` or `pva://DEMO:A`, or a `formula://<name>` reference to a screen formula. A rule's `targetProperty` can't name a `pv-channel` prop.

**The list of IR widget types is the set of files in this directory.** No separate list is kept, so there's nothing to fall out of sync. `absolute-canvas` is the document root, and `unknown-widget` is the converter's placeholder for source classes it has no definition for. Both are real types and have files here.

**In v0.1 the prop schemas describe props but aren't enforced.** They're carried over from the Beaver registry, and some of their constraints would reject real screens:
- `"type": "number"` rejects macro values like `"$(PREC)"`;
- several `required` lists don't match what the builder writes.

Conformance doesn't test props against them yet; see [Known gaps](#known-gaps-v01).

## Conformance

Each case in `conformance/` is self-contained (format: `conformance/case.schema.json`):

```json
{
  "description": "On a screen every macro needs a default.",
  "valid": false,
  "errors": [{ "rule": "macro-default-required", "instancePath": "/macros/0" }],
  "screen": { "...": "the document under test" }
}
```

An implementation runs its validator on `screen` and compares:
- **Level 1:** whether the screen counts as valid matches `valid`.
- **Level 2:** level 1, and every expected error appears among the reported errors with the same `rule` and `instancePath`. Extra reported errors are allowed.

Each invalid case breaks exactly one rule. Schema-error locations were chosen to be the same in ajv and Python `jsonschema`.

### Current implementations

| Implementation | Result | Notes |
|---|---|---|
| `tools/check.py` (reference) | Level 2, 34/34 | |
| `@slaclab/canopy-screen-ir` `validate()` | Level 1, 22/22 | Schema error paths match. Semantic errors are returned as plain strings without a rule id or path |
| `pydm-converter-tool` `validate_screen_json` | 16/22 | Schema only: it accepts the six semantically invalid cases, so the converter can emit screens that `validate()` rejects |

## Using the spec from an SDK

1. Copy the files you need into the SDK, pinned to a release tag of this repo, and record the tag.
2. In the SDK's CI, check that the copied files are byte-identical to that tag, and run the conformance cases.
3. When this repo releases, open a PR in each SDK that bumps the pin. The SDK's CI shows whether it still conforms.

Don't edit copied files in an SDK. Change the spec here first. Keep a copy of [LICENSE.md](LICENSE.md) next to them: the license requires redistributed source to keep its notice.

## Versions

- **Release tags** (`vMAJOR.MINOR.PATCH`) version the whole repo. A major bump means some consumer must change.
- **`schemaVersion`** in a document changes only when the document format changes. It isn't tied to the release number.
- **A widget definition's `version`** tracks that type's `propSchema`.

## Changing the spec

1. Open a PR here. Update the schema or definitions, add conformance cases for the change, and run `uv run tools/check.py`.
2. Note the change in `CHANGELOG.md` and tag a release.
3. Bump the pin in each consumer.

## Known gaps (v0.1)

- **`pv-toggle` has no definition.** Both the screen builder and the runtime accept it.
- **Don't validate props against the prop schemas yet, in CI or anywhere else.** In particular, don't enforce their `required` lists. Some don't match real screens: `text-label` requires `text`, but the builder also imports text labels that only have `label`. Enforcing them first needs:
  - a rule that number props also accept macro strings;
  - `required` lists reconciled against what the converter and the builder actually write;
  - consistent key naming. `pv-slider` uses `min`/`max` while `pv-spinbox` uses `minValue`/`maxValue`.
- **The root type and `supportsChildren` aren't enforced.** `absolute-canvas` belongs at the root and nowhere else, and only types with `supportsChildren: true` should have `children`, but no semantic rule checks either yet. A document with a `pv-label` root, or a `pv-led` with children, passes validation.
- **Implementation results below the reference row are against the 22 cases of v0.1.0.**
- **Mixed drafts.** The prop schemas are draft-07 and the document schema is 2020-12.
- **No conformance cases for macro expansion, rule evaluation or `props.actions` handling yet.** Today only the runtime implements them.
- **No conformance cases for color schemes or flattening.** `tools/check.py` checks `color-scheme.schema.json` only as a schema, and `canopy-default` isn't in this repo yet.

## Where the initial content came from

- `screen-ir/screen-ir.schema.json`: copied from `slaclab/canopy-sdk-js` `packages/screen-ir/schema/` at `74fc229` (package version 0.1.2). Only `description` strings have changed since: they named the TypeScript package as the owner and `validate()` as the place the semantic rules live. The structure is identical.
- `screen-ir/widgets/*.json`: the IR fields (`id`, `version`, `description`, `propSchema`, `supportsPv`, `supportsRules`, `supportsChildren`) taken from `slaclab/canopy` `widget-registry-data/widgets/*.json` at `01bcd7d`. The values are unchanged (checked field by field), with two exceptions:
  - The `pv-button` and `absolute-canvas` prop schemas come from `pydm-converter-tool`'s bundled registry at `019ee4e`, which adds the props the converter has emitted since 1.0.6 (nine on `pv-button`, `backgroundColor` on `absolute-canvas`). Both definitions are version 1.1.0, so they aren't confused with Beaver's 1.0.0.
  - Every `propSchema.$schema` is the draft-07 meta-schema's identifier, `http://json-schema.org/draft-07/schema#`. Beaver used `https://json-schema.org/draft-07/schema`, which ajv and Python `jsonschema` don't recognize.

  The files are not byte-identical: the other fields were dropped and the JSON was reformatted. `unknown-widget.json` is new; it describes what `pydm-converter-tool` emits.
- `conformance/screen-ir/validate/*.json`: new. They cover the cases in `canopy-sdk-js`'s `validate.test.ts` and the semantic rules in its `validate.ts`.

Background: slaclab/canopy-sdk-js#4 and slaclab/canopy-screen-runtime#6.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). canopy-spec is distributed under the terms in [LICENSE.md](LICENSE.md).

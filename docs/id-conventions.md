# ID Conventions

Single, repo-wide naming convention for every entity that needs a stable,
greppable, human-mentionable identifier. Adopted in Phase 1 of the v0.5 →
v1.0 evolution. Existing artifacts in older campaigns are NOT migrated;
the convention applies to all new IDs going forward.

## Format

| Prefix      | Format        | Used by              | Where                                     |
| ----------- | ------------- | -------------------- | ----------------------------------------- |
| `F`         | `F\d{3,4}`    | harness-plan         | `.harness/features.json`                  |
| `CHG-`      | `CHG-\d{3,}`  | harness-plan (Ph. 4) | `.harness/changes/CHG-NNN/` and feature `change_units[]` |
| `REQ-`      | `REQ-\d{3,}`  | harness-engineering  | `.engineering/discovery/requirements.json` |
| `DES-`      | `DES-\d{3,}`  | harness-engineering  | `.engineering/design/design-spec.json`    |
| `ADR-`      | `ADR-\d{3,}`  | harness-engineering  | `.engineering/architecture/adrs/`         |
| `IMPL-`     | `IMPL-\d{3,}` | harness-engineering  | `.engineering/implementation/IMPL-NNN/`   |
| `TEST-`     | `TEST-\d{3,}` | harness-engineering  | `.engineering/test/test-report.json`      |
| `REL-`      | `REL-\d{3,}`  | harness-engineering  | `.engineering/release/release-checklist.json` |
| `OPS-`      | `OPS-\d{3,}`  | harness-engineering  | `.engineering/ops/`                       |
| `EVAL-`     | `EVAL-\d{3,}` | harness-engineering (Ph. 5) | `.engineering/eval/cases/`         |

## Rules

1. **Three-digit minimum, no leading-zero strip.** `F001` not `F1`. Reason:
   sortable as strings without padding logic.
2. **Numbers are local to their prefix.** `F001` and `IMPL-001` are unrelated
   IDs that happen to share `001`. Don't assume cross-prefix relationships
   from the number.
3. **IDs are immutable.** Once assigned, an ID never changes — even after a
   feature is renamed, redesigned, or merged. Stale IDs are marked
   `archived` or `superseded`, not renumbered.
4. **No skipping or reuse.** When you delete `F003`, the next new feature is
   `F005`, not `F003`. ID gaps are intentional history.
5. **Human-mentionable.** Always pronounce as "F oh-oh-three" or "CHG dash
   oh-oh-one". Don't use IDs the LLM cannot disambiguate from common words.

## Why F is bare and the rest are prefixed

Historical accident — `F` predates the convention. `F` stays bare because
features are the most-mentioned entity in harness-plan campaigns; the dash
saves no information when there's only one entity per file. All other types
share files or directories with multiple entity types, so the prefix is
load-bearing.

## Validation

`harness_lib.validate_feature` and `engineering_lib`'s schema validators
include an ID-format lint:

- Phase 1 (current): warn on non-conforming IDs. Existing campaigns continue
  to validate.
- Phase 4: upgrade to error for IDs created after Phase 4. Old IDs grandfathered.

## Adding a new prefix

If a new entity type needs an ID:

1. Pick a 3-5 letter uppercase prefix that doesn't collide with existing rows.
2. Add a row to this table in the same PR that introduces the entity.
3. Add a regex check in the relevant validator.
4. Update `dedup-matrix.md` if the new entity has a capability associated
   with it.

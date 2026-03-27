# Skill: agility-planning-level-cleanup

## When To Use
- User wants to clean up, close, or audit a planning level (Scope) in Digital.ai Agility
- User wants to find Sub-Features, Features, or Epics that are ready to close
- User wants to bulk-update statuses or close portfolio items on a planning level
- User asks about work item completion status across a planning level

## Overview

This skill provides workflows and Python scripts for auditing and cleaning up
a planning level (Scope) in Digital.ai Agility. The typical workflow is:

1. **Fetch** all portfolio items (Sub-Features/Features/Epics) on a planning level
2. **Fetch** all children (Stories + Defects) for those portfolio items
3. **Analyze** which portfolio items have all children closed and are ready to close
4. **Update** statuses (e.g. mark as "Completed")
5. **Close** portfolio items via the Inactivate operation

## Prerequisites

- `AGILITY_TOKEN` environment variable must be set with a valid bearer token
- Python 3.8+ with no external dependencies (uses only stdlib: json, urllib, os, sys)
- Network access to `https://www7.v1host.com/V1Production`

## API Reference

### Base URL
```
https://www7.v1host.com/V1Production
```

### Authentication
```
Authorization: Bearer {AGILITY_TOKEN}
```

### Key Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `rest-1.v1/Data/{AssetType}?sel=...&where=...&page=...` | GET | Query assets |
| `rest-1.v1/Data/{AssetType}/{id}` | POST | Update an asset |
| `rest-1.v1/Data/{AssetType}/{id}?op=Inactivate` | POST | Close (inactivate) an asset |

### Asset Types

| Type | Description |
|---|---|
| `Epic` | Portfolio items (Epic, Feature, Sub-Feature -- distinguished by `Category.Name`) |
| `Story` | User stories / backlog items |
| `Defect` | Bugs / defects |
| `Scope` | Projects / planning levels |
| `EpicStatus` | Status values for Epics |
| `EpicCategory` | Category values (Epic, Feature, Sub-Feature, etc.) |

### Asset States

| Code | State |
|---|---|
| 0 | Future |
| 64 | Active |
| 128 | Closed |
| 208 | Broken Down |
| 255 | Deleted |

### Known Status OIDs (DevOps)

| OID | Name |
|---|---|
| `EpicStatus:1905281` | Completed |
| `EpicStatus:670492` | In Progress |
| `EpicStatus:670502` | Review |
| `EpicStatus:559703` | Discovery |
| `EpicStatus:1905275` | Breakdown |
| `EpicStatus:2200973` | Not Doing |

### Known Scope OIDs (DevOps)

| Scope | OID | Parent |
|---|---|---|
| DevOps (root) | `Scope:1731677` | -- |
| 26.1 DevOps | `Scope:3234178` | DevOps |

### Where Clause Syntax
- Equality: `Field='Value'`
- Not equal: `Field!='Value'`
- AND: `;` separator
- OR: `|` separator
- Nested: `Super.Category.Name='Sub-Feature'`
- Always exclude deleted: `AssetState!='255'`

### Efficient Bulk Querying

**Do NOT query children one-by-one per portfolio item.** Instead, use scope-level
filters with nested attributes:

```
# Get ALL Stories under Sub-Features in a scope -- single query
GET rest-1.v1/Data/Story?sel=Name,Number,Status.Name,Super.Number,...
    &where=Scope='Scope:3234178';Super.Category.Name='Sub-Feature';AssetState!='255'
    &page=500,0
```

This fetches all Stories whose parent is a Sub-Feature in that scope. Paginate with
`page=500,0`, `page=500,500`, etc. until you get fewer than pageSize results.

The same works for Defects:
```
GET rest-1.v1/Data/Defect?sel=...&where=Scope='...';Super.Category.Name='Sub-Feature';AssetState!='255'&page=500,0
```

### Updating Status

```bash
curl -s -X POST \
  -H "Authorization: Bearer $AGILITY_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/Epic/{oid_num}" \
  -d '{"Attributes": {"Status": {"value": "EpicStatus:1905281", "act": "set"}}}'
```

### Closing (Inactivating) an Asset

```bash
curl -s -X POST \
  -H "Authorization: Bearer $AGILITY_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/Epic/{oid_num}?op=Inactivate" \
  -d '{}'
```

## Python Scripts

All scripts are in `scripts/` relative to this skill. They use only Python stdlib
and read `AGILITY_TOKEN` from the environment.

### scripts/fetch_subfeatures.py

Fetches all portfolio items of a given category on a planning level and saves to JSON.

```bash
python3 scripts/fetch_subfeatures.py --scope "26.1 DevOps" --category Sub-Feature --output subfeatures.json
```

### scripts/fetch_children.py

Fetches all Stories and Defects under portfolio items of a given category on a
planning level. Uses bulk scope-level queries (not per-item).

```bash
python3 scripts/fetch_children.py --scope "26.1 DevOps" --parent-category Sub-Feature --output children.json
```

### scripts/analyze_readiness.py

Reads the subfeatures and children JSON files, computes which portfolio items
are ready to close (all children closed), and outputs a report.

```bash
python3 scripts/analyze_readiness.py --subfeatures subfeatures.json --children children.json --output report.json
```

### scripts/update_status.py

Updates the status of portfolio items. Supports dry-run mode.

```bash
# Dry run (preview only)
python3 scripts/update_status.py --input report.json --status Completed --dry-run

# Execute
python3 scripts/update_status.py --input report.json --status Completed
```

### scripts/close_items.py

Closes (Inactivates) portfolio items. Supports dry-run mode and pre-checks.

```bash
# Dry run
python3 scripts/close_items.py --input report.json --dry-run

# Execute
python3 scripts/close_items.py --input report.json
```

## Typical Workflow

```bash
# 1. Fetch Sub-Features
python3 scripts/fetch_subfeatures.py --scope "26.1 DevOps" --category Sub-Feature -o sf.json

# 2. Fetch all children (Stories + Defects) in bulk
python3 scripts/fetch_children.py --scope "26.1 DevOps" --parent-category Sub-Feature -o children.json

# 3. Analyze readiness
python3 scripts/analyze_readiness.py --subfeatures sf.json --children children.json -o report.json

# 4. Mark ready items as Completed (dry-run first)
python3 scripts/update_status.py --input report.json --status Completed --filter ready_to_close --dry-run
python3 scripts/update_status.py --input report.json --status Completed --filter ready_to_close

# 5. Close items (dry-run first)
python3 scripts/close_items.py --input report.json --filter ready_to_close --dry-run
python3 scripts/close_items.py --input report.json --filter ready_to_close
```

## Agent Guidance

- Always start with a dry-run before making changes
- Always verify results after updates by re-querying
- The `--filter` flag on update/close scripts supports: `ready_to_close`, `all_completed`, `no_children`, or a comma-separated list of Epic numbers (e.g., `E-19816,E-19822`)
- Include Defects in analysis -- they also block closing
- Use `page=500,0` for bulk queries, paginate until results < pageSize
- Remember: changing Status to "Completed" and Closing (Inactivate) are separate operations
- UI links use: `https://www7.v1host.com/V1Production/assetdetail.v1?number={Number}`

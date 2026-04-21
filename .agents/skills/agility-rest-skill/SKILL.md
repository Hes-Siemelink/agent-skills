---
name: agility-rest-skill
description: Use when you need to query or manage Portfolio Items (Epics/Features), Stories, and Defects in Digital.ai Agility via the rest-1.v1 Data API.
---

# agility-rest

## When To Use
- User asks to query, create, or update work items in Digital.ai Agility.
- You need data from `rest-1.v1/Data/{AssetType}` for Epics, Stories, Defects, or related assets.
- Asset types include: `Epic`, `Story`, `Defect`, `Scope`, `Team`, `Timebox`, `Theme`, `Member`, `EpicCategory`, `StoryCategory`, `Request`.
- Bearer token auth is required (`Authorization: Bearer ...`).

## Concepts

### Asset Types
| Asset Type | Description | Common Aliases |
|---|---|---|
| `Defect` | Bugs / defects | Bug |
| `Epic` | Portfolio Items (Epics, Features, Initiatives, Sub-Features) | Portfolio Item, PI |
| `EpicCategory` | Category values for Epics | - |
| `Request` | Change requests | - |
| `Scope` | Projects / planning levels | Project |
| `Story` | User stories / backlog items | Backlog Item |
| `Team` | Teams within a scope | - |
| `Theme` | Themes / tags | Tag |
| `Timebox` | Sprints / iterations | Sprint, Iteration |

### Epic Categories
Epics are distinguished by `Category.Name`. Known values:
Area, Capability, Enhancement, **Epic**, **Feature**, Feature Outcome, Goal, Impact Epic, **Initiative**, Marketing Commitment, Marketing Program, Milestone, New Feature, Non-Functional, Release Themes, Request, **Sub-Feature**, Sub-Initiative, Team Commitment

When the user says "Epics" they typically mean `Category.Name='Epic'`. When they say "Features" they mean `Category.Name='Feature'`.

### Asset States
| Value | Meaning |
|---|---|
| 0 | Future (not yet started) |
| 64 | Active |
| 128 | Closed |
| 200 | Template |
| 208 | Broken Down |
| 255 | Deleted |

To exclude deleted items, add `AssetState!='255'` to `where` clauses.

### Status vs Asset State
**Status** and **Asset State** are independent concepts in Agility:
- **Asset State** is the lifecycle state (Future/Active/Closed/Deleted) — controls visibility and is changed via operations like Inactivate
- **Status** is a workflow field (e.g. "In Progress", "Done", "Completed") — set by users/teams to indicate progress

A Story can have Status = "Done" but Asset State = Active (64). This means the work is finished but the item has not been formally closed. When assessing completion, check **both** fields.

Common Story/Defect status values in DevOps: `Done`, `DONE`, `Not Doing`, `To Do`, `TO DO`, `In Progress`, `Testing`, `TESTING`, `Developing`, `Code Review`, `QA Done`, `Review`, `Abandoned`, `Product Review`, `Completed`

Common Epic/Sub-Feature status values: `Completed`, `In Progress`, `Review`, `Discovery`, `Breakdown`, `Not Doing`

Common Request status values: `Reviewed`, `Approved`, `Rejected`, `Future Consideration`, `Need More Information`, `Not Planned`, `Aligns with upcoming Discovery projects`, `Already Supported`, `TRB - Idea`, `TRB - Discovery`, `TRB - Technology Review`, `TRB - Commitment`, `TRB - Alpha`, `TRB - Beta`, `TRB - GA`

Request priority values: `Low`, `Medium`, `High`, `Must`, `Should`, `Could`, `Blocker`, `Critical`, `Major`, `Minor`, `Trivial`

Request category values: `New Feature`, `Tweak`, `Question`, `Enhancement`, `Platform`, `Change`

Request resolution reason values: `Implemented`, `Rejected`, `Supported`, `Move to Backlog`

### Key Relationships
- `Epic.Super` -> parent Epic (for Epic-to-Epic hierarchy)
- `Story.Super` / `Defect.Super` -> parent Epic
- `Epic.Scope` / `Story.Scope` -> owning Scope (planning level)
- `Story.Team` / `Defect.Team` -> assigned Team
- `Story.Timebox` / `Defect.Timebox` -> Sprint/Iteration
- `Epic.Subs` -> child Epics (multi-value)
- `Epic.ChildrenMeAndDown` -> all descendant stories/defects
- `Request.Scope` -> owning Scope (planning level)
- `Request.Owner` -> assigned Member
- `Request.SpurredBy` -> Epic that triggered this Request
- `Request.PrimaryWorkitems` -> linked Stories/Defects (multi-value)
- `Request.Epics` -> linked Epics (multi-value)
- `Request.Issues` -> linked Issues (multi-value)

### Cross-Scope Children (Critical)
**Children (Stories/Defects) can live in a different Scope than their parent Epic.**
For example, a Sub-Feature in "26.1 DevOps" (Scope:3234178) may have children in:
- "DevOps" (parent scope, Scope:1731677)
- "UXD" (completely different scope)
- "DevOps Delivery", "25.3-DevOps", etc.

When querying children by scope (`Scope='Scope:3234178'`), you will **miss children in other scopes**. To get ALL children regardless of scope, filter on the **parent's scope** instead:
```
# WRONG — misses cross-scope children:
where=Scope='Scope:3234178';Super.Category.Name='Sub-Feature'

# CORRECT — gets all children whose parent is in the scope:
where=Super.Scope='Scope:3234178';Super.Category.Name='Sub-Feature'
```

This can be a massive difference. In 26.1 DevOps, scope-only queries returned 607 children while `Super.Scope` queries returned 1,100 — nearly double.

### Scope (Planning Level) — DevOps Example
The DevOps planning level has **two Scopes** both named "DevOps". The correct one for Epics is:
- **Scope OID**: `Scope:1731677`
- Filter with: `Scope='Scope:1731677'`
- Or by name: `Scope.Name='DevOps'` (may match both — prefer OID for precision)

Sub-scopes (sprints/releases) like "26.1 DevOps", "26.2 DevOps" are children of `Scope:1731677`.

## API Base URL
`https://www7.v1host.com/V1Production`

## REST API Patterns

### Query (GET)
```
GET {baseUrl}/rest-1.v1/Data/{AssetType}?sel={fields}&where={filter}&sort={sort}&page={limit},{offset}
```

Headers:
```
Authorization: Bearer {token}
Accept: application/json
```

### Query by OID (GET single asset)
```
GET {baseUrl}/rest-1.v1/Data/{AssetType}/{id}?sel={fields}
```

### Create (POST)
```
POST {baseUrl}/rest-1.v1/Data/{AssetType}
Content-Type: application/json
Authorization: Bearer {token}

{
  "Attributes": {
    "Name": { "value": "...", "act": "set" },
    "Scope": { "value": "Scope:1731677", "act": "set" },
    ...
  }
}
```

### Update (POST to existing asset)
```
POST {baseUrl}/rest-1.v1/Data/{AssetType}/{id}
Content-Type: application/json
Authorization: Bearer {token}

{
  "Attributes": {
    "FieldName": { "value": "...", "act": "set" }
  }
}
```

## Where Clause Syntax
- Equality: `Field='Value'`
- Not equal: `Field!='Value'`
- AND: use `;` separator — `Field1='A';Field2='B'`
- OR: use `|` separator — `Field1='A'|Field1='B'`
- Empty/null: `Field=''`
- Not empty: `Field!=''`
- Relation by OID: `Scope='Scope:1731677'`
- Nested attribute: `Scope.Name='DevOps'`, `Category.Name='Epic'`, `Status.Name='Done'`
- Combine: `Scope='Scope:1731677';Category.Name='Epic';AssetState!='255'`

## Sort Syntax
- Ascending: `Name`
- Descending: `-Name`

## Paging
- `page={pageSize},{offset}` — e.g., `page=50,0` returns first 50

## Inputs
- `baseUrl` (required): e.g. `https://www7.v1host.com/V1Production`
- `bearerToken` (required): API token for `Authorization: Bearer ...`
- `assetType` (required): One of `Epic`, `Story`, `Defect`, `Scope`, `Team`, `Timebox`, etc.
- `action` (optional, default `query`): `query`, `get`, `create`, `update`
- `id` (optional): Asset numeric ID for `get` or `update` actions
- `sel` (optional): Comma-delimited field selection
- `where` (optional): Filter clause
- `sort` (optional): Sort expression
- `limit` (optional, default `50`): Page size
- `offset` (optional, default `0`): Paging offset
- `find` (optional): Free text search
- `findin` (optional): Fields to search in
- `body` (optional): JSON body for `create`/`update` actions
- `noPrompt` (optional, default `false`): Non-interactive mode

## Execution

### Using curl
Agents and users can use curl directly. This is often simpler for one-off queries than writing a script.

**Query Epics in DevOps scope:**
```bash
curl -s -H "Authorization: Bearer <token>" \
  -H "Accept: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/Epic?sel=Name,Number,Status.Name,Category.Name,Scope.Name&where=Scope%3D%27Scope%3A1731677%27%3BCategory.Name%3D%27Epic%27%3BAssetState!%3D%27255%27&sort=-ChangeDate&page=20,0"
```

**Query Stories under a specific Epic:**
```bash
curl -s -H "Authorization: Bearer <token>" \
  -H "Accept: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/Story?sel=Name,Number,Status.Name,Team.Name,Timebox.Name,Estimate&where=Super%3D%27Epic%3A12345%27%3BAssetState!%3D%27255%27&sort=-ChangeDate&page=100,0"
```

**Query orphaned Stories (no parent Epic) in a sub-scope:**
```bash
curl -s -H "Authorization: Bearer <token>" \
  -H "Accept: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/Story?sel=Name,Number,Status.Name,Team.Name,Timebox.Name&where=Scope.Name%3D%2726.1+DevOps%27%3BSuper%3D%27%27%3BAssetState!%3D%27255%27&sort=-ChangeDate&page=200,0"
```

**Create a Feature under a parent Epic:**
```bash
curl -s -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/Epic" \
  -d '{
    "Attributes": {
      "Name": { "value": "My New Feature - 26.3", "act": "set" },
      "Scope": { "value": "Scope:1731677", "act": "set" },
      "Super": { "value": "Epic:17160", "act": "set" },
      "Category": { "value": "EpicCategory:148", "act": "set" }
    }
  }'
```

**Query all EpicCategory values:**
```bash
curl -s -H "Authorization: Bearer <token>" \
  -H "Accept: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/EpicCategory?sel=Name&page=100,0"
```

**Query Teams in a scope:**
```bash
curl -s -H "Authorization: Bearer <token>" \
  -H "Accept: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/Team?sel=Name&where=Scope.Name%3D%27DevOps%27&page=100,0"
```

**Query Requests in a scope:**
```bash
curl -s -H "Authorization: Bearer <token>" \
  -H "Accept: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/Request?sel=Name,Number,Status.Name,Priority.Name,Category.Name,Owner.Name,RequestedBy,Scope.Name&where=Scope%3D%27Scope%3A1731677%27%3BAssetState!%3D%27255%27&sort=-ChangeDate&page=50,0"
```

**Query a single Request by number:**
```bash
curl -s -H "Authorization: Bearer <token>" \
  -H "Accept: application/json" \
  "https://www7.v1host.com/V1Production/rest-1.v1/Data/Request?sel=Name,Number,Status.Name,Priority.Name,Category.Name,Owner.Name,RequestedBy,Description,Resolution,ResolutionReason.Name,Scope.Name,SpurredBy.Name,SpurredBy.Number&where=Number%3D%27R-12511%27"
```

## UI URL Pattern

### Preferred: by display number (no OID lookup needed)
Use the `assetdetail.v1` endpoint with the display number directly:
```
https://www7.v1host.com/V1Production/assetdetail.v1?number={Number}
```
Examples:
- Epic E-19550: `https://www7.v1host.com/V1Production/assetdetail.v1?number=E-19550`
- Story S-125773: `https://www7.v1host.com/V1Production/assetdetail.v1?number=S-125773`
- Defect D-42068: `https://www7.v1host.com/V1Production/assetdetail.v1?number=D-42068`
- Request R-12511: `https://www7.v1host.com/V1Production/assetdetail.v1?number=R-12511`

This pattern works for all asset types (Epics, Stories, Defects, Requests) and does not require an OID lookup. **Always prefer this pattern when generating UI links.**

### Alternative: by OID
If you already have the OID from an API response, you can also link directly:
```
https://www7.v1host.com/V1Production/{AssetType}.mvc/Summary?oidToken={AssetType}:{id}
```
Examples:
- Epic E-19550: `https://www7.v1host.com/V1Production/Epic.mvc/Summary?oidToken=Epic:3370498`
- Story S-125773: `https://www7.v1host.com/V1Production/Story.mvc/Summary?oidToken=Story:3459190`

Note: The `{id}` in this URL is the **OID number** (e.g., `3370498`), NOT the display number (e.g., `19550`). Use the `ID` or `id` field from API responses to construct these URLs.

## Configuration File
Default config file path: `./agility-rest.config.json` (next to `SKILL.md`)

Use this file to define:
- default selected fields per asset type
- default sort per asset type
- default page size
- default scope filter (DevOps)
- known fields per asset type
- guardrails (read-only mode, strict field validation)

Guardrail defaults:
- `guardrails.readOnlyByDefault: true` -> blocks POST/PUT unless `--action create` or `--action update` is explicit
- `guardrails.allowedEndpointPattern` -> only allows `/rest-1.v1/Data/<AssetType>` patterns
- `guardrails.strictFields: false` -> off by default (Agility has many fields; use config lists as guidance, not enforcement)

Override precedence (highest to lowest):
1. CLI args
2. Environment variables
3. Config file defaults
4. Built-in fallback defaults

## Environment Variables
- `AGILITY_BASE_URL`
- `AGILITY_BEARER_TOKEN`
- `AGILITY_DEFAULT_SCOPE`

## Agent Guidance
When an agent uses this skill, it should:
- **Always exclude deleted assets** by including `AssetState!='255'` in `where` clauses
- **Use OID references** for Scope, Super, Category relations (e.g., `Scope='Scope:1731677'`) for precision
- **Use `Category.Name`** to distinguish Epic subtypes: `Category.Name='Epic'`, `Category.Name='Feature'`, etc.
- **Check `Super=''`** to find orphaned Stories/Defects with no parent Epic
- **Use `Number`** field for display-friendly IDs (e.g., E-19550, S-125773, D-45678, R-12511)
- **Use `assetdetail.v1?number=` URLs** for UI links (e.g., `assetdetail.v1?number=E-19550`) — no OID lookup needed
- **Use `id`** field from response only when OID-based references are needed (e.g., for API relation filters like `Super='Epic:12345'`)
- **Keep `limit` conservative** (20-50) unless bulk retrieval is needed
- **URL-encode `where` clauses** in curl — single quotes become `%27`, semicolons become `%3B`, equals becomes `%3D`, spaces become `+`
- **For creation**, always set `Scope` explicitly — it is NOT inherited from parent
- **For Epics/Features**, set `Category` to the correct `EpicCategory` OID (e.g., `EpicCategory:148` for Feature)
- **For Requests**, recommended `sel` fields are: `Name,Number,Status.Name,Priority.Name,Category.Name,Owner.Name,RequestedBy,Scope.Name` — add `Description,Resolution,ResolutionReason.Name,SpurredBy.Name,SpurredBy.Number` when detail is needed
- **Requests use `Scope` not `Super`** — unlike Stories/Defects they do not have a parent Epic hierarchy; link to Epics via `SpurredBy` (single) or `Epics` (multi-value)
- **Request status is separate from resolution** — `Status` tracks workflow state (Approved, Rejected, etc.); `ResolutionReason` records how it was closed (Implemented, Supported, etc.); check both when assessing outcome
- **Use `Super.Scope` for cross-scope children queries** — children often live in different scopes than their parent Epic. Filter on `Super.Scope='Scope:...'` instead of `Scope='Scope:...'` to get all children regardless of their own scope
- **Distinguish Status from Asset State** — a Story with Status="Done" and AssetState=Active is finished work not yet formally closed. Check both fields when assessing completion
- **Include `Accept: application/json` header on POST requests** — without it, the response may be empty or XML
- Present results in **concise tabular format** when possible
- Include **UI links** for key assets using the URL pattern above

### Common EpicCategory OIDs (DevOps)
These are reference values; verify with a query if unsure:
- Epic: query `EpicCategory?where=Name='Epic'`
- Feature: `EpicCategory:148`
- Initiative: query `EpicCategory?where=Name='Initiative'`
- Sub-Feature: query `EpicCategory?where=Name='Sub-Feature'`

### DevOps Teams (26.1 scope)
Alphas, Apollo, Dry Bones, FI Deploy, Integrations, Judo, Lambdas, Leonardo, Mario, PM DevOps, Robotix, Sonic, Vanguard

### Known Scope OIDs (DevOps)

| Scope | OID | Parent |
|---|---|---|
| DevOps (root) | `Scope:1731677` | — |
| 26.1 DevOps | `Scope:3234178` | DevOps |

### Known Status OIDs (DevOps Epics)

| OID | Name |
|---|---|
| `EpicStatus:1905281` | Completed |
| `EpicStatus:670492` | In Progress |
| `EpicStatus:670502` | Review |
| `EpicStatus:559703` | Discovery |
| `EpicStatus:1905275` | Breakdown |
| `EpicStatus:2200973` | Not Doing |

### Known Request Lookup OIDs

**RequestStatus**

| OID | Name |
|---|---|
| `RequestStatus:170` | Reviewed |
| `RequestStatus:171` | Approved |
| `RequestStatus:172` | Rejected |
| `RequestStatus:1651461` | Future Consideration |
| `RequestStatus:1651810` | Need More Information |
| `RequestStatus:1655799` | Not Planned |
| `RequestStatus:1655800` | Aligns with upcoming Discovery projects |
| `RequestStatus:1655805` | Already Supported |
| `RequestStatus:2588718` | TRB - Idea |
| `RequestStatus:2588725` | TRB - Discovery |
| `RequestStatus:2588728` | TRB - Technology Review |
| `RequestStatus:2588729` | TRB - Commitment |
| `RequestStatus:2588730` | TRB - Alpha |
| `RequestStatus:2588731` | TRB - Beta |
| `RequestStatus:2588732` | TRB - GA |

**RequestPriority**

| OID | Name |
|---|---|
| `RequestPriority:167` | Low |
| `RequestPriority:168` | Medium |
| `RequestPriority:169` | High |
| `RequestPriority:1652662` | Must |
| `RequestPriority:1652663` | Could |
| `RequestPriority:1652664` | Should |
| `RequestPriority:1905260` | Blocker |
| `RequestPriority:1905261` | Critical |
| `RequestPriority:1905262` | Major |
| `RequestPriority:1905263` | Minor |
| `RequestPriority:1905264` | Trivial |

**RequestCategory**

| OID | Name |
|---|---|
| `RequestCategory:173` | New Feature |
| `RequestCategory:174` | Tweak |
| `RequestCategory:175` | Question |
| `RequestCategory:29226` | Enhancement |
| `RequestCategory:29227` | Platform |
| `RequestCategory:3288539` | Change |

**RequestResolution**

| OID | Name |
|---|---|
| `RequestResolution:185` | Implemented |
| `RequestResolution:186` | Rejected |
| `RequestResolution:1470086` | Supported |
| `RequestResolution:2582763` | Move to Backlog |

## Output
Success prints JSON:
- `requestUrl`: final URL used
- `status`: HTTP status
- `contentType`: response content type
- `total`: total matching assets (from API `total` field)
- `assets`: flattened display-ready asset rows
- `data`: parsed JSON response (raw API shape)

Errors print JSON to stderr:
- `code`: `INPUT | NETWORK | AUTH | INTERNAL`
- `message`
- `details`

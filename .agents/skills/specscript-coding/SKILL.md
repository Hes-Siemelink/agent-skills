---
name: specscript-coding
description: Writes SpecScript .spec.yaml scripts. Covers YAML structure, document separators, commands, variables, HTTP requests, control flow, and common pitfalls. Use when writing new .spec.yaml files, converting code to SpecScript, or when the user asks to create a SpecScript script.
compatibility: Requires access to SpecScript specification files for reference.
metadata:
  author: specscript
  version: "1.0"
---

## Overview

SpecScript scripts are YAML files (`.spec.yaml`) where dictionary keys are commands executed in sequence. The key
insight: YAML is both data format and code format, blurring the line between the two (like Lisp). This means YAML's
key-uniqueness constraint is the main pitfall.

## Documentation

The `specification/` directory is the authoritative reference. Key paths:

| Topic | Path |
|-------|------|
| Language overview | `specification/language/` |
| YAML scripts & `---` | `specification/language/SpecScript Yaml Scripts.spec.md` |
| Variables | `specification/language/Variables.spec.md` |
| Eval syntax | `specification/language/Eval syntax.spec.md` |
| Packages & imports | `specification/language/Packages.spec.md` |
| Best practices | `specification/language/SpecScript Best Practices.spec.md` |
| Input schema | `specification/commands/core/script-info/Input schema.spec.md` |
| All commands | `specification/commands/core/` |

Read these spec files directly when you need details beyond what this skill covers.

## Script structure

Every script follows this pattern:

```yaml
Script info: Short description of what this script does

Input schema:
  type: object
  properties:
    name:
      description: A parameter
      default: default-value
    token:
      description: A secret from environment
      env: MY_ENV_VAR

---
# Commands go here, separated by ---
Print: Hello ${name}!
```

- `Script info` — one-line description (shown in `--help`)
- `Input schema` — JSON Schema subset defining CLI flags. Properties become `--flag-name` on the command line.
  Supported keywords: `description`, `default`, `enum`, `type`, `env`, `condition`, plus top-level `required` array.
- `---` — YAML document separator, used between command groups
- Input properties are accessible as `${name}` or `${input.name}`

## The golden rule: `---` separators

**SpecScript's biggest pitfall is duplicate YAML keys.** YAML silently drops duplicate keys — no error, just data loss.

**Always use `---` between command groups.** Specifically required when:
- The same command name appears twice (`Print`, `If`, `For each`, `Size`, etc.)
- The same modifier key appears twice (`As` is the most common trap)
- You want a visual section break

```yaml
# WRONG — duplicate As key, second silently wins
GET: /api/users
As: ${users}

For each:
  ${u} in: ${users}
  Output: ${u.name}
As: ${names}
```

```yaml
# CORRECT
GET: /api/users
As: ${users}

---
For each:
  ${u} in: ${users}
  Output: ${u.name}
As: ${names}
```

**When in doubt, add `---`.** It never hurts. Prefer it over top-level list syntax (`- Command: ...`) which adds
visual noise.

**Do not use `# --- section ---` comments.** The `---` separator itself is the section divider.

## Variables

```yaml
# Assign
${greeting}: Hello World

# Use anywhere via interpolation
Print: ${greeting}

# Nested path access (JavaScript-like)
Print: ${user.address.city}
Print: ${list[0].name}

# Bracket notation for keys with dots/spaces
Print: ${data["Status.Name"]}

# Capture command output into a variable
GET: /api/users
As: ${users}

# Built-in variables
# ${output}        — result of the last command
# ${input}         — all input parameters as an object
# ${input.name}    — specific input parameter
# ${env.VAR_NAME}  — OS environment variable (read-only)
# ${SCRIPT_HOME}   — directory containing the current script
# ${PWD}           — absolute path to the working directory where spec was launched
```

**There is no `.size` or `.length` property on lists.** Use the `Size` command instead.

## HTTP requests

```yaml
# Simple GET
GET: /api/items

# GET with headers and base URL
Http request defaults:
  url: https://api.example.com
  headers:
    Authorization: Bearer ${token}
    Accept: application/json

---
GET: /items?page=1&limit=50
As: ${response}

# POST with body
POST:
  url: /items
  body:
    name: New Item
    status: active

# Save response to file
GET:
  url: /items
  save as: out/items.json
```

Query parameters go inline in the URL string — there is no separate `params` property.

## Control flow

### For each — looping and list transformation

```yaml
# Basic loop
For each:
  ${name} in:
    - Alice
    - Bob
  Print: Hello ${name}!

# Transform a list (each iteration's Output is collected)
For each:
  ${user} in: ${users}
  Output:
    name: ${user.name}
    email: ${user.email}
As: ${clean_users}

# Loop over ${output} (implicit variable ${item})
For each:
  Print: ${item.name}
```

### If — conditionals

```yaml
If:
  item: ${status}
  equals: active
  then:
    Output: Running
  else:
    Output: Stopped

# Negation
If:
  not:
    empty: ${data}
  then:
    Print: Has data

# Multiple conditions with "in"
If:
  item: ${status}
  in:
    - active
    - pending
  then:
    Output: ${item}
```

Multiple commands inside `then`/`else` are just additional keys in the same object:

```yaml
If:
  not:
    empty: ${items}
  then:
    Print: Processing...
    For each:
      ${item} in: ${items}
      Print: ${item.name}
```

### Filtering a list

There is no `Filter` command. Use `For each` + `If` with `Output`:

```yaml
For each:
  ${item} in: ${all_items}
  If:
    item: ${item.status}
    equals: active
    then:
      Output: ${item}
As: ${active_items}
```

### Repeat — loop until condition

```yaml
${offset}: 0
${all}: []

Repeat:
  GET: /api/items?offset=${offset}
  As: ${result}

  Add to:
    ${all}: ${result.items}
    ${offset}: 50

  until:
    empty: ${result.items}

Output: ${all}
```

### When — multi-branch conditional

Executes only the first matching condition (short-circuits). Useful when you have many branches:

```yaml
When:
  - item: ${status}
    equals: active
    then:
      Output: Running
  - item: ${status}
    equals: paused
    then:
      Output: Suspended
  - else:
      Output: Unknown
```

### Do — grouping commands

`Do` executes a list of commands. Useful when you need to call the same command multiple times inside a block
(avoids duplicate YAML keys). The output is the result of the last command.

```yaml
Do:
  - Print: Step 1
  - Print: Step 2
  - Output: done
```

## Data manipulation

```yaml
# Count items
Size: ${my_list}
As: ${count}

# Append to list
Add to:
  ${list}: ${new_item}

# Append to string
Add to:
  ${text}: " more text"

# Sort
Sort:
  by: name

# Look up a value in a map
Find:
  path: ${key}
  in: ${lookup_table}

# Write file
Write file:
  file: output.md
  content: ${report}
```

## SQLite

```yaml
# Query (returns list of rows)
SQLite:
  file: my.db
  query: SELECT * FROM items WHERE status = '${status}'

# Update (executes statements)
SQLite:
  file: my.db
  update:
    - INSERT INTO items (name) VALUES ('${name}')
```

Variable references in single quotes (`'${var}'`) are automatically converted to prepared statement parameters,
preventing SQL injection. Use `SQLite defaults` to set a default database file for all subsequent commands.

## Eval syntax — inline command execution

Prefix a command with `/` to evaluate it inline within a data structure. Eliminates intermediate variables when a
value is used only once:

```yaml
# Instead of:
Size: ${features}
As: ${count}
Print: "Found ${count} items"

# Use:
Print:
  Items found:
    /Size: ${features}
```

## Common patterns

### API client script

```yaml
Script info: Fetch data from an API

Input schema:
  type: object
  properties:
    base-url:
      description: API base URL
      default: https://api.example.com
    token:
      description: API token
      env: API_TOKEN

---
Http request defaults:
  url: ${input.base-url}
  headers:
    Authorization: Bearer ${token}

---
GET: /api/items
As: ${items}

---
For each:
  ${item} in: ${items}
  Print: "${item.id}: ${item.name}"
```

### Building text incrementally

```yaml
${report}: |
  # Report Title

  Generated for ${user_name}

---
Add to:
  ${report}: "\n## Section 1\n\nContent here\n"

---
If:
  not:
    empty: ${extra_data}
  then:
    Add to:
      ${report}: "\n## Extra\n\n${extra_data}\n"

---
Write file:
  file: ${input.output}
  content: ${report}
```

## Organizing scripts as CLI commands

Directories become CLI command groups. Files become subcommands:

```
features/
├── specscript-config.yaml    # optional: description, imports, connections
├── list.spec.yaml            # → spec features list
└── create.spec.yaml          # → spec features create
```

- `spec features list` runs `features/list.spec.yaml`
- `spec features` shows interactive command chooser
- `spec features --help` lists available subcommands
- The `.spec.yaml` extension is optional when invoking

Add `specscript-config.yaml` for a directory description:

```yaml
Script info: Manage features in Agility
```

Scripts in the same directory can call each other as commands. File `create-item.spec.yaml` becomes command
`Create item` in sibling scripts.

## Packages and imports

Directories can be organized into packages for cross-project reuse.

Declare a package in `specscript-config.yaml`:

```yaml
Package info: My utility scripts
```

Import commands from packages in the consumer's `specscript-config.yaml`:

```yaml
imports:
  my-utils:
    - helper-command
    - "**"             # or import everything recursively
```

- Local imports use `./` prefix: `./lib:` imports from a sibling directory
- Aliases: `- sub/hi: { as: greet }` renames an imported command
- Package discovery: enclosing package > `--package-path` flag > `SPECSCRIPT_PACKAGE_PATH` env var > `~/.specscript/packages/`

See `specification/language/Packages.spec.md` for full details.

## Connections

Named connections store default settings (base URLs, database files) in `specscript-config.yaml`:

```yaml
connections:
  My API:
    Http request defaults:
      url: https://api.example.com
      headers:
        Authorization: Bearer ${token}
  My DB:
    SQLite defaults:
      file: data/app.db
```

Activate a connection in a script:

```yaml
Connect to: My API
```

## Rules

- **Always validate YAML:** After writing a `.spec.yaml` file, check for duplicate keys at the same level in each
  `---`-separated document. This is the most common source of silent bugs.
- **`As` is a top-level key**, not part of the command above it. Two commands that each use `As` need a `---` between
  them.
- **No `.size`/`.length` on lists** — use the `Size` command.
- **No `Filter` command** — use `For each` + `If` + `Output` to filter lists.
- **No `Join` command** — use `For each` + `Add to` to build strings from lists.
- **No `params` on HTTP requests** — query parameters go inline in the URL.
- **Commands are case-insensitive** but by convention start with a capital letter.
- **`Print` does not change `${output}`** — it only writes to console. Avoid using `Print` for status messages;
  prefer structured `Output` at the end of the script.
- **End scripts with a defined `Output`** — SpecScript prints the final output automatically, and calling scripts
  can pick it up. Use descriptive YAML keys to build a summary instead of `Print` statements:
  ```yaml
  Output:
    report: results.md
    items-processed: 42
    status: complete
  ```
- **Use `env:` in Input schema** for secrets and environment-dependent config, not `${env.VAR}` inline.
- **Don't rely on `${output}` from distant commands** — any intervening command (including eval syntax) may change it.
  Capture it immediately with `As: ${var}` if you need it later.
- **Never name an input parameter `output`** — it collides with the built-in `${output}` variable and is ambiguous
  (JSON data? stdout? filename?). Use a specific name like `report-file` instead.

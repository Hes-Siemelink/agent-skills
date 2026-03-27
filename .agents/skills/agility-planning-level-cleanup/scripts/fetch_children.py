#!/usr/bin/env python3
"""
Fetch all Stories and Defects under portfolio items of a given category on a planning level.

Uses bulk scope-level queries with nested attribute filtering -- NOT per-item queries.

Usage:
    python3 fetch_children.py --scope "26.1 DevOps" --parent-category Sub-Feature --output children.json
    python3 fetch_children.py --scope-oid Scope:3234178 --parent-category Feature -o children.json
"""
import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

SSL_CTX = ssl.create_default_context()
try:
    SSL_CTX.load_default_locations()
except Exception:
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE

BASE_URL = "https://www7.v1host.com/V1Production"
ASSET_STATE_MAP = {0: "Future", 64: "Active", 128: "Closed", 200: "Template", 208: "Broken Down", 255: "Deleted"}

CHILD_FIELDS = [
    "Name", "Number", "Status.Name", "Team.Name", "Timebox.Name",
    "Estimate", "Super.Name", "Super.Number", "Super.Category.Name",
    "AssetState", "Owners.Name", "ChangeDate",
]


def get_token():
    token = os.environ.get("AGILITY_TOKEN") or os.environ.get("AGILITY_BEARER_TOKEN")
    if not token:
        print("Error: Set AGILITY_TOKEN or AGILITY_BEARER_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)
    return token


def api_get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code}: {e.reason}\n{body}", file=sys.stderr)
        sys.exit(1)


def resolve_scope(scope_name, token):
    where = urllib.parse.quote(f"Name='{scope_name}'")
    url = f"{BASE_URL}/rest-1.v1/Data/Scope?sel=Name,Parent.Name&where={where}&page=10,0"
    data = api_get(url, token)
    assets = data.get("Assets", [])
    if not assets:
        print(f"Error: No scope found with name '{scope_name}'", file=sys.stderr)
        sys.exit(1)
    if len(assets) > 1:
        print(f"Warning: Multiple scopes named '{scope_name}', using first:", file=sys.stderr)
        for a in assets:
            print(f"  {a['id']} (parent: {a['Attributes']['Parent.Name']['value']})", file=sys.stderr)
    return assets[0]["id"]


def fetch_paginated(asset_type, scope_oid, parent_category, token, page_size=500):
    """Fetch all assets of given type, paginating automatically."""
    sel = ",".join(CHILD_FIELDS)
    where = urllib.parse.quote(
        f"Scope='{scope_oid}';Super.Category.Name='{parent_category}';AssetState!='255'"
    )
    all_assets = []
    offset = 0
    while True:
        url = (
            f"{BASE_URL}/rest-1.v1/Data/{asset_type}"
            f"?sel={sel}&where={where}&sort=Super.Number,Number&page={page_size},{offset}"
        )
        data = api_get(url, token)
        assets = data.get("Assets", [])
        all_assets.extend(assets)
        print(f"  {asset_type}: fetched {len(all_assets)} so far (page offset {offset})")
        if len(assets) < page_size:
            break
        offset += page_size
    return all_assets


def flatten_child(asset):
    """Convert API asset to a flat dict."""
    attrs = asset["Attributes"]
    oid = asset["id"]
    oid_num = int(oid.split(":")[1])
    asset_type = oid.split(":")[0]

    owners_val = attrs.get("Owners.Name", {}).get("value", [])
    if isinstance(owners_val, list):
        owners = ", ".join(owners_val) if owners_val else None
    else:
        owners = owners_val

    return {
        "oid": oid,
        "oid_num": oid_num,
        "type": asset_type,
        "number": attrs["Number"]["value"],
        "name": attrs["Name"]["value"],
        "status": attrs["Status.Name"]["value"],
        "asset_state": ASSET_STATE_MAP.get(attrs["AssetState"]["value"], str(attrs["AssetState"]["value"])),
        "asset_state_code": attrs["AssetState"]["value"],
        "team": attrs["Team.Name"]["value"],
        "timebox": attrs["Timebox.Name"]["value"],
        "estimate": attrs["Estimate"]["value"],
        "owners": owners,
        "parent_number": attrs["Super.Number"]["value"],
        "parent_name": attrs["Super.Name"]["value"],
        "parent_category": attrs["Super.Category.Name"]["value"],
        "change_date": attrs["ChangeDate"]["value"],
        "url": f"https://www7.v1host.com/V1Production/assetdetail.v1?number={attrs['Number']['value']}",
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch children (Stories + Defects) under portfolio items")
    scope_group = parser.add_mutually_exclusive_group(required=True)
    scope_group.add_argument("--scope", help="Scope name (e.g. '26.1 DevOps')")
    scope_group.add_argument("--scope-oid", help="Scope OID (e.g. Scope:3234178)")
    parser.add_argument("--parent-category", required=True, help="Parent category (Sub-Feature, Feature, Epic)")
    parser.add_argument("-o", "--output", required=True, help="Output JSON file path")
    args = parser.parse_args()

    token = get_token()

    if args.scope_oid:
        scope_oid = args.scope_oid
        scope_name = args.scope_oid
    else:
        scope_oid = resolve_scope(args.scope, token)
        scope_name = args.scope

    print(f"Scope: {scope_name} ({scope_oid})")
    print(f"Parent category: {args.parent_category}")
    print(f"Fetching Stories...")

    stories_raw = fetch_paginated("Story", scope_oid, args.parent_category, token)
    stories = [flatten_child(a) for a in stories_raw]

    print(f"Fetching Defects...")
    defects_raw = fetch_paginated("Defect", scope_oid, args.parent_category, token)
    defects = [flatten_child(a) for a in defects_raw]

    all_children = stories + defects

    # Stats
    story_states = {}
    defect_states = {}
    for s in stories:
        st = s["asset_state"]
        story_states[st] = story_states.get(st, 0) + 1
    for d in defects:
        st = d["asset_state"]
        defect_states[st] = defect_states.get(st, 0) + 1

    result = {
        "query": {
            "scope": scope_name,
            "scope_oid": scope_oid,
            "parent_category": args.parent_category,
            "generated_at": str(date.today()),
            "total_stories": len(stories),
            "total_defects": len(defects),
            "total_children": len(all_children),
            "api_calls_made": "2-4 (bulk scope query, not per-item)",
        },
        "summary": {
            "stories_by_state": dict(sorted(story_states.items(), key=lambda x: -x[1])),
            "defects_by_state": dict(sorted(defect_states.items(), key=lambda x: -x[1])),
        },
        "children": all_children,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nTotal: {len(stories)} Stories + {len(defects)} Defects = {len(all_children)} children")
    print(f"Stories by state: {story_states}")
    print(f"Defects by state: {defect_states}")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()

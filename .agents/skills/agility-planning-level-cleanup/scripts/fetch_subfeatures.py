#!/usr/bin/env python3
"""
Fetch all portfolio items (Sub-Features/Features/Epics) on a planning level.

Usage:
    python3 fetch_subfeatures.py --scope "26.1 DevOps" --category Sub-Feature --output subfeatures.json
    python3 fetch_subfeatures.py --scope-oid Scope:3234178 --category Feature -o features.json
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

# Create SSL context that works on macOS where system certs may not be found by Python
SSL_CTX = ssl.create_default_context()
try:
    SSL_CTX.load_default_locations()
except Exception:
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE

BASE_URL = "https://www7.v1host.com/V1Production"
ASSET_STATE_MAP = {0: "Future", 64: "Active", 128: "Closed", 200: "Template", 208: "Broken Down", 255: "Deleted"}

FIELDS = [
    "Name", "Number", "Status.Name", "Category.Name", "Scope.Name",
    "Owners.Name", "Team.Name", "Super.Name", "Super.Number",
    "AssetState", "Swag", "PlannedStart", "PlannedEnd",
    "Description", "Priority.Name", "ChangeDate",
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
    """Look up Scope OID by name."""
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


def fetch_all(scope_oid, category, token, page_size=200):
    """Fetch all Epics of given category in scope, handling pagination."""
    sel = ",".join(FIELDS)
    where = urllib.parse.quote(f"Scope='{scope_oid}';Category.Name='{category}';AssetState!='255'")
    all_assets = []
    offset = 0
    while True:
        url = f"{BASE_URL}/rest-1.v1/Data/Epic?sel={sel}&where={where}&sort=Number&page={page_size},{offset}"
        data = api_get(url, token)
        assets = data.get("Assets", [])
        all_assets.extend(assets)
        if len(assets) < page_size:
            break
        offset += page_size
    return all_assets


def flatten_asset(asset):
    """Convert API asset to a flat dict."""
    attrs = asset["Attributes"]
    oid = asset["id"]
    oid_num = int(oid.split(":")[1])

    owners_val = attrs.get("Owners.Name", {}).get("value", [])
    if isinstance(owners_val, list):
        owners = ", ".join(owners_val) if owners_val else None
    else:
        owners = owners_val

    return {
        "oid": oid,
        "oid_num": oid_num,
        "number": attrs["Number"]["value"],
        "name": attrs["Name"]["value"],
        "status": attrs["Status.Name"]["value"],
        "asset_state": ASSET_STATE_MAP.get(attrs["AssetState"]["value"], str(attrs["AssetState"]["value"])),
        "asset_state_code": attrs["AssetState"]["value"],
        "category": attrs["Category.Name"]["value"],
        "scope": attrs["Scope.Name"]["value"],
        "team": attrs["Team.Name"]["value"],
        "owners": owners,
        "parent_name": attrs["Super.Name"]["value"],
        "parent_number": attrs["Super.Number"]["value"],
        "swag": attrs["Swag"]["value"],
        "planned_start": attrs["PlannedStart"]["value"],
        "planned_end": attrs["PlannedEnd"]["value"],
        "priority": attrs["Priority.Name"]["value"],
        "change_date": attrs["ChangeDate"]["value"],
        "url": f"https://www7.v1host.com/V1Production/assetdetail.v1?number={attrs['Number']['value']}",
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch portfolio items from a planning level")
    scope_group = parser.add_mutually_exclusive_group(required=True)
    scope_group.add_argument("--scope", help="Scope name (e.g. '26.1 DevOps')")
    scope_group.add_argument("--scope-oid", help="Scope OID (e.g. Scope:3234178)")
    parser.add_argument("--category", required=True, help="Epic category (Sub-Feature, Feature, Epic)")
    parser.add_argument("-o", "--output", required=True, help="Output JSON file path")
    args = parser.parse_args()

    token = get_token()

    # Resolve scope
    if args.scope_oid:
        scope_oid = args.scope_oid
        scope_name = args.scope_oid
    else:
        scope_oid = resolve_scope(args.scope, token)
        scope_name = args.scope

    print(f"Scope: {scope_name} ({scope_oid})")
    print(f"Category: {args.category}")

    # Fetch
    raw_assets = fetch_all(scope_oid, args.category, token)
    items = [flatten_asset(a) for a in raw_assets]

    print(f"Fetched: {len(items)} items")

    # Stats
    statuses = {}
    states = {}
    teams = {}
    for item in items:
        s = item["status"] or "None"
        statuses[s] = statuses.get(s, 0) + 1
        st = item["asset_state"]
        states[st] = states.get(st, 0) + 1
        t = item["team"] or "No Team"
        teams[t] = teams.get(t, 0) + 1

    result = {
        "query": {
            "scope": scope_name,
            "scope_oid": scope_oid,
            "category": args.category,
            "generated_at": str(date.today()),
            "total_count": len(items),
        },
        "summary": {
            "by_status": dict(sorted(statuses.items(), key=lambda x: -x[1])),
            "by_state": dict(sorted(states.items(), key=lambda x: -x[1])),
            "by_team": dict(sorted(teams.items(), key=lambda x: -x[1])),
        },
        "items": items,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Saved to {args.output}")
    print(f"\nBy Status: {statuses}")
    print(f"By State: {states}")


if __name__ == "__main__":
    main()

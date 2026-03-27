#!/usr/bin/env python3
"""
Update the status of portfolio items in Agility.

Reads a report JSON from analyze_readiness.py and updates matching items.

Usage:
    python3 update_status.py --input report.json --status Completed --dry-run
    python3 update_status.py --input report.json --status Completed
    python3 update_status.py --input report.json --status Completed --filter ready_to_close
    python3 update_status.py --input report.json --status Completed --filter E-19816,E-19822
"""
import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

SSL_CTX = ssl.create_default_context()
try:
    SSL_CTX.load_default_locations()
except Exception:
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE

BASE_URL = "https://www7.v1host.com/V1Production"

# Known status OIDs -- extend as needed
STATUS_OIDS = {
    "Completed": "EpicStatus:1905281",
    "In Progress": "EpicStatus:670492",
    "Review": "EpicStatus:670502",
    "Discovery": "EpicStatus:559703",
    "Breakdown": "EpicStatus:1905275",
    "Not Doing": "EpicStatus:2200973",
    "Done": "EpicStatus:302558",
}


def get_token():
    token = os.environ.get("AGILITY_TOKEN") or os.environ.get("AGILITY_BEARER_TOKEN")
    if not token:
        print("Error: Set AGILITY_TOKEN or AGILITY_BEARER_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)
    return token


def api_post(url, body, token):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode() if e.fp else ""
        print(f"  ERROR HTTP {e.code}: {e.reason}\n  {resp_body}", file=sys.stderr)
        return None


def resolve_status_oid(status_name, token):
    """Look up status OID if not in cache."""
    if status_name in STATUS_OIDS:
        return STATUS_OIDS[status_name]

    where = urllib.parse.quote(f"Name='{status_name}'")
    url = f"{BASE_URL}/rest-1.v1/Data/EpicStatus?sel=Name&where={where}&page=10,0"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, context=SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error looking up status '{status_name}': HTTP {e.code}", file=sys.stderr)
        sys.exit(1)

    assets = data.get("Assets", [])
    if not assets:
        print(f"Error: No EpicStatus found with name '{status_name}'", file=sys.stderr)
        print("Known statuses:", ", ".join(STATUS_OIDS.keys()), file=sys.stderr)
        sys.exit(1)

    oid = assets[0]["id"]
    STATUS_OIDS[status_name] = oid
    return oid


def filter_items(analysis, filter_str):
    """Filter analysis items based on filter string."""
    if not filter_str:
        return analysis

    # Check if it's a disposition filter
    dispositions = {"ready_to_close", "has_open_children", "no_children", "already_closed", "all_completed"}
    if filter_str in dispositions:
        if filter_str == "all_completed":
            return [a for a in analysis if a.get("status") == "Completed" and a.get("asset_state_code") != 128]
        return [a for a in analysis if a.get("disposition") == filter_str]

    # Otherwise treat as comma-separated list of numbers
    numbers = {n.strip() for n in filter_str.split(",")}
    return [a for a in analysis if a["number"] in numbers]


def main():
    parser = argparse.ArgumentParser(description="Update status of portfolio items")
    parser.add_argument("--input", required=True, help="Report JSON file (from analyze_readiness.py)")
    parser.add_argument("--status", required=True, help="Target status name (e.g. Completed)")
    parser.add_argument("--filter", help="Filter: ready_to_close, has_open_children, no_children, or comma-separated numbers")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing")
    args = parser.parse_args()

    token = get_token()

    with open(args.input) as f:
        report = json.load(f)

    analysis = report.get("analysis", [])
    items = filter_items(analysis, args.filter)

    if not items:
        print("No items match the filter criteria.")
        return

    # Skip items that already have this status
    needs_update = [a for a in items if a.get("status") != args.status]
    already_set = len(items) - len(needs_update)

    status_oid = resolve_status_oid(args.status, token)

    print(f"Status: {args.status} ({status_oid})")
    print(f"Filter: {args.filter or 'all'}")
    print(f"Matched: {len(items)} items")
    print(f"Already '{args.status}': {already_set}")
    print(f"Need update: {len(needs_update)}")
    if args.dry_run:
        print(f"\n*** DRY RUN - no changes will be made ***\n")
    print()

    success = 0
    failed = 0
    for item in needs_update:
        number = item["number"]
        oid_num = item["oid_num"]
        current = item.get("status") or "None"
        name = item["name"]

        if args.dry_run:
            print(f"  [DRY RUN] {number}: {current} -> {args.status}  ({name[:50]})")
        else:
            url = f"{BASE_URL}/rest-1.v1/Data/Epic/{oid_num}"
            body = {"Attributes": {"Status": {"value": status_oid, "act": "set"}}}
            result = api_post(url, body, token)
            if result:
                print(f"  [OK] {number}: {current} -> {args.status}  ({name[:50]})")
                success += 1
            else:
                print(f"  [FAIL] {number}: {current} -> {args.status}  ({name[:50]})")
                failed += 1

    print()
    if args.dry_run:
        print(f"Dry run complete. {len(needs_update)} items would be updated.")
    else:
        print(f"Done. Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    main()

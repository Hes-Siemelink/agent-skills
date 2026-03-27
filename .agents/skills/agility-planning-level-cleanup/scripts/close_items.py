#!/usr/bin/env python3
"""
Close (Inactivate) portfolio items in Agility.

Reads a report JSON from analyze_readiness.py and closes matching items
using the Inactivate operation.

Usage:
    python3 close_items.py --input report.json --dry-run
    python3 close_items.py --input report.json --filter ready_to_close --dry-run
    python3 close_items.py --input report.json --filter ready_to_close
    python3 close_items.py --input report.json --filter E-19816,E-19822
"""
import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

SSL_CTX = ssl.create_default_context()
try:
    SSL_CTX.load_default_locations()
except Exception:
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE

BASE_URL = "https://www7.v1host.com/V1Production"


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


def filter_items(analysis, filter_str):
    """Filter analysis items based on filter string."""
    if not filter_str:
        return analysis

    dispositions = {"ready_to_close", "has_open_children", "no_children", "already_closed"}
    if filter_str in dispositions:
        return [a for a in analysis if a.get("disposition") == filter_str]

    numbers = {n.strip() for n in filter_str.split(",")}
    return [a for a in analysis if a["number"] in numbers]


def main():
    parser = argparse.ArgumentParser(description="Close (Inactivate) portfolio items")
    parser.add_argument("--input", required=True, help="Report JSON file (from analyze_readiness.py)")
    parser.add_argument("--filter", help="Filter: ready_to_close, or comma-separated numbers")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing")
    parser.add_argument("--force", action="store_true", help="Close even if item has open children (use with caution)")
    args = parser.parse_args()

    token = get_token()

    with open(args.input) as f:
        report = json.load(f)

    analysis = report.get("analysis", [])
    items = filter_items(analysis, args.filter)

    if not items:
        print("No items match the filter criteria.")
        return

    # Exclude already closed
    closeable = [a for a in items if a.get("asset_state_code") != 128]
    already_closed = len(items) - len(closeable)

    # Safety check: warn about items with open children
    has_open = [a for a in closeable if a.get("active_children", 0) > 0]
    if has_open and not args.force:
        print(f"WARNING: {len(has_open)} items have open children and will be skipped.")
        print("Use --force to close them anyway.\n")
        closeable = [a for a in closeable if a.get("active_children", 0) == 0 or a.get("all_children_closed")]

    print(f"Filter: {args.filter or 'all'}")
    print(f"Matched: {len(items)} items")
    print(f"Already closed: {already_closed}")
    print(f"Will close: {len(closeable)}")
    if args.dry_run:
        print(f"\n*** DRY RUN - no changes will be made ***\n")
    print()

    success = 0
    failed = 0
    for item in closeable:
        number = item["number"]
        oid_num = item["oid_num"]
        state = item.get("asset_state", "?")
        name = item["name"]
        children_info = f"{item.get('closed_children', 0)}/{item.get('total_children', 0)} children closed"

        if args.dry_run:
            print(f"  [DRY RUN] {number}: {state} -> Closed  ({children_info})  {name[:45]}")
        else:
            url = f"{BASE_URL}/rest-1.v1/Data/Epic/{oid_num}?op=Inactivate"
            result = api_post(url, {}, token)
            if result:
                print(f"  [OK] {number}: {state} -> Closed  ({children_info})  {name[:45]}")
                success += 1
            else:
                print(f"  [FAIL] {number}: {state} -> Closed  ({children_info})  {name[:45]}")
                failed += 1

    print()
    if args.dry_run:
        print(f"Dry run complete. {len(closeable)} items would be closed.")
    else:
        print(f"Done. Success: {success}, Failed: {failed}")
        if success > 0:
            print("Tip: Re-run fetch_subfeatures.py and analyze_readiness.py to refresh the data.")


if __name__ == "__main__":
    main()

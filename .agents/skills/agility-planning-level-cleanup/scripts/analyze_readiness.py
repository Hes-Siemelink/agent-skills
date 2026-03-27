#!/usr/bin/env python3
"""
Analyze readiness of portfolio items for closing.

Cross-references subfeatures with their children to determine which items
have all children closed and are ready to close.

Usage:
    python3 analyze_readiness.py --subfeatures subfeatures.json --children children.json --output report.json
"""
import argparse
import json
import sys
from datetime import date


def main():
    parser = argparse.ArgumentParser(description="Analyze portfolio item readiness for closing")
    parser.add_argument("--subfeatures", required=True, help="Subfeatures JSON file (from fetch_subfeatures.py)")
    parser.add_argument("--children", required=True, help="Children JSON file (from fetch_children.py)")
    parser.add_argument("-o", "--output", required=True, help="Output report JSON file")
    args = parser.parse_args()

    with open(args.subfeatures) as f:
        sf_data = json.load(f)
    with open(args.children) as f:
        ch_data = json.load(f)

    items = sf_data["items"]
    children = ch_data["children"]

    # Group children by parent
    children_by_parent = {}
    for c in children:
        pn = c["parent_number"]
        if pn not in children_by_parent:
            children_by_parent[pn] = []
        children_by_parent[pn].append(c)

    # Analyze each item
    analysis = []
    counts = {
        "already_closed": 0,
        "ready_to_close": 0,
        "has_open_children": 0,
        "no_children": 0,
        "total": len(items),
    }

    for item in items:
        item_children = children_by_parent.get(item["number"], [])
        total = len(item_children)
        closed = sum(1 for c in item_children if c["asset_state_code"] == 128)
        active = sum(1 for c in item_children if c["asset_state_code"] == 64)
        stories = [c for c in item_children if c["type"] == "Story"]
        defects = [c for c in item_children if c["type"] == "Defect"]

        is_already_closed = item["asset_state_code"] == 128
        all_children_closed = total > 0 and closed == total
        ready_to_close = all_children_closed and not is_already_closed

        open_children = [
            {
                "number": c["number"],
                "name": c["name"],
                "type": c["type"],
                "status": c["status"],
                "asset_state": c["asset_state"],
            }
            for c in item_children
            if c["asset_state_code"] != 128
        ]

        if is_already_closed:
            counts["already_closed"] += 1
            disposition = "already_closed"
        elif ready_to_close:
            counts["ready_to_close"] += 1
            disposition = "ready_to_close"
        elif total == 0:
            counts["no_children"] += 1
            disposition = "no_children"
        else:
            counts["has_open_children"] += 1
            disposition = "has_open_children"

        entry = {
            "number": item["number"],
            "name": item["name"],
            "oid": item["oid"],
            "oid_num": item["oid_num"],
            "status": item["status"],
            "asset_state": item["asset_state"],
            "asset_state_code": item["asset_state_code"],
            "team": item["team"],
            "owners": item["owners"],
            "total_children": total,
            "total_stories": len(stories),
            "total_defects": len(defects),
            "closed_children": closed,
            "active_children": active,
            "all_children_closed": all_children_closed,
            "disposition": disposition,
            "open_children": open_children,
            "url": item["url"],
        }
        analysis.append(entry)

    # Sort: ready_to_close first, then has_open_children, then no_children, then already_closed
    disposition_order = {"ready_to_close": 0, "has_open_children": 1, "no_children": 2, "already_closed": 3}
    analysis.sort(key=lambda x: (disposition_order.get(x["disposition"], 99), x["number"]))

    result = {
        "query": {
            "subfeatures_file": args.subfeatures,
            "children_file": args.children,
            "generated_at": str(date.today()),
            "scope": sf_data["query"]["scope"],
            "category": sf_data["query"]["category"],
        },
        "counts": counts,
        "analysis": analysis,
    }

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    # Print summary
    print(f"Planning Level Cleanup Report: {sf_data['query']['scope']}")
    print(f"Category: {sf_data['query']['category']}")
    print(f"{'=' * 60}")
    print(f"Total items:          {counts['total']}")
    print(f"Already closed:       {counts['already_closed']}")
    print(f"Ready to close:       {counts['ready_to_close']}")
    print(f"Has open children:    {counts['has_open_children']}")
    print(f"No children:          {counts['no_children']}")
    print()

    ready = [a for a in analysis if a["disposition"] == "ready_to_close"]
    if ready:
        print(f"READY TO CLOSE ({len(ready)}):")
        print(f"{'-' * 60}")
        for a in ready:
            team = a["team"] or "No Team"
            owners = a["owners"] or "No Owner"
            print(f"  {a['number']:8s} | {a['status'] or 'None':<12s} | {team:<16s} | {owners}")
            print(f"           {a['name']}")
            print(f"           Children: {a['total_stories']}S + {a['total_defects']}D = {a['total_children']} (all closed)")
        print()

    open_items = [a for a in analysis if a["disposition"] == "has_open_children"]
    if open_items:
        print(f"HAS OPEN CHILDREN ({len(open_items)}):")
        print(f"{'-' * 60}")
        for a in open_items:
            open_count = len(a["open_children"])
            print(f"  {a['number']:8s} | {a['name'][:50]}")
            print(f"           {a['closed_children']}/{a['total_children']} closed, {open_count} open")

    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()

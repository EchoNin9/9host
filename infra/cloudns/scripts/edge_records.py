#!/usr/bin/env python3
"""T-24: idempotent upsert of the echo9.net edge records via the ClouDNS API.

Replaces the OpenTofu cloudns_dns_record resources (provider ClouDNS/cloudns 1.0.10
cannot read records back). Only these four hosts in zone echo9.net are ever read or
written; nothing else in the zone (@, www, MX, NS, TXT, ACM CNAMEs) is touched.

  app           CNAME -> root output cloudfront_production_domain (Admin SPA)
  sites-origin  CNAME -> root output cloudfront_sites_domain (Cloudflare for SaaS upstream)
  preview       CNAME -> root output cloudfront_landing_domain (9host-landing)
  tools         WR 301 -> https://tools.e9.cx

Usage (from repo root; root infra must be initialised so `tofu output` works):
  AWS_PROFILE=echo9 AWS_REGION=us-east-1 .venv/bin/python infra/cloudns/scripts/edge_records.py           # dry run
  AWS_PROFILE=echo9 AWS_REGION=us-east-1 .venv/bin/python infra/cloudns/scripts/edge_records.py --apply   # write

Credentials come from AWS secret 9host-cloudns ({"auth_id", "password"}); never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

ZONE = "echo9.net"
TTL = 300
API = "https://api.cloudns.net/dns"
SECRET_ID = "9host-cloudns"
INFRA_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# CNAME host -> root `tofu output` name; tools is a static 301 web redirect.
CNAME_OUTPUTS = {
    "app": "cloudfront_production_domain",
    "sites-origin": "cloudfront_sites_domain",
    "preview": "cloudfront_landing_domain",
}
TOOLS = {"type": "WR", "value": "https://tools.e9.cx", "ttl": TTL,
         "redirect_type": 301, "frame": 0, "save_path": 0}
HOSTS = ("app", "sites-origin", "tools", "preview")


def desired_records() -> dict[str, dict]:
    out = subprocess.run(["tofu", f"-chdir={INFRA_DIR}", "output", "-json"],
                         check=True, capture_output=True, text=True).stdout
    outputs = json.loads(out)
    desired = {}
    for host, name in CNAME_OUTPUTS.items():
        value = (outputs.get(name) or {}).get("value")
        if not value:
            sys.exit(f"root tofu output {name} is missing/empty; refusing to continue")
        desired[host] = {"type": "CNAME", "value": value.rstrip(".").lower(), "ttl": TTL}
    desired["tools"] = dict(TOOLS)
    return desired


def credentials() -> dict:
    import boto3  # from the repo .venv

    region = os.environ.get("AWS_REGION", "us-east-1")
    raw = boto3.client("secretsmanager", region_name=region).get_secret_value(SecretId=SECRET_ID)
    creds = json.loads(raw["SecretString"])
    return {"auth-id": creds["auth_id"], "auth-password": creds["password"]}


def call(endpoint: str, creds: dict, params: dict):
    data = urllib.parse.urlencode({**creds, "domain-name": ZONE, **params}).encode()
    with urllib.request.urlopen(f"{API}/{endpoint}", data=data, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    if isinstance(body, dict) and body.get("status") == "Failed":
        sys.exit(f"ClouDNS {endpoint} failed: {body.get('statusDescription')}")
    return body


def current_records(creds: dict, host: str) -> list[dict]:
    body = call("records.json", creds, {"host": host})
    rows = body.values() if isinstance(body, dict) else body  # [] when none
    return [r for r in rows if isinstance(r, dict) and r.get("host") == host]


def normalise(rec: dict) -> dict:
    """ClouDNS API row -> comparable dict (same shape as desired_records)."""
    n = {"type": rec.get("type"), "ttl": int(rec.get("ttl") or 0)}
    if n["type"] == "WR":
        n["value"] = rec.get("record", "")
        n["redirect_type"] = int(rec.get("redirect_type") or 0)
        n["frame"] = int(rec.get("frame") or 0)
        n["save_path"] = int(rec.get("save_path") or 0)
    else:
        n["value"] = (rec.get("record") or "").rstrip(".").lower()
    return n


def write_params(host: str, want: dict) -> dict:
    p = {"host": host, "record": want["value"], "ttl": want["ttl"]}
    if want["type"] == "WR":
        p.update({"redirect-type": want["redirect_type"], "frame": want["frame"],
                  "save-path": want["save_path"]})
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="show diff only (default)")
    mode.add_argument("--apply", action="store_true", help="create/update records that differ")
    args = ap.parse_args()

    desired = desired_records()
    creds = credentials()
    changes = 0
    for host in HOSTS:
        want = desired[host]
        rows = current_records(creds, host)
        same_type = [r for r in rows if r.get("type") == want["type"]]
        if len(same_type) > 1:
            print(f"{host}: {len(same_type)} {want['type']} records exist; refusing to guess (fix by hand)")
            changes += 1
            continue
        other = [r.get("type") for r in rows if r.get("type") != want["type"]]
        if other and not same_type:
            print(f"{host}: conflicting record types {other} exist; refusing to touch (fix by hand)")
            changes += 1
            continue
        have = normalise(same_type[0]) if same_type else None
        print(f"{host}.{ZONE}\n  current: {json.dumps(have, sort_keys=True)}\n  desired: {json.dumps(want, sort_keys=True)}")
        if have == want:
            print("  -> no change")
            continue
        changes += 1
        if not args.apply:
            print("  -> would " + ("update" if have else "create"))
            continue
        if have:
            call("mod-record.json", creds, {"record-id": same_type[0]["id"], **write_params(host, want)})
            print("  -> updated")
        else:
            call("add-record.json", creds, {"record-type": want["type"], **write_params(host, want)})
            print("  -> created")
    print(f"\n{changes} change(s) {'applied' if args.apply else 'pending (dry run; use --apply)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

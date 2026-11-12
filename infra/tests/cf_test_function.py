#!/usr/bin/env python3
"""T-21: smoke-test a CloudFront Function in the REAL cloudfront-js-2.0 runtime before publishing.

node tests cannot catch runtime-only errors (T-18's "await in arguments" SyntaxError passed them
and 503'd every site). CI runs this BEFORE `tofu apply` publishes the function:

  1. upload the new code to the function's DEVELOPMENT stage (LIVE is untouched),
  2. `test-function` a mapped-host and an unmapped-host viewer-request event,
  3. always restore DEVELOPMENT to the LIVE code/config, so tofu still sees the code change
     and updates + publishes exactly as before.

Exit 1 on FunctionErrorMessage or an unexpected result.
Usage: python infra/tests/cf_test_function.py [--name 9host-site-content] [--code infra/cf-site-content.js]
"""
import argparse
import json
import re
import sys

import boto3

MAPPED_URI = re.compile(r"^/[a-z0-9_-]+/[A-Za-z0-9_-]+/published/current/index\.html$")


def event(host):
    return {
        "version": "1.0",
        "context": {"eventType": "viewer-request"},
        "viewer": {"ip": "192.0.2.1"},
        "request": {"method": "GET", "uri": "/", "querystring": {}, "headers": {"host": {"value": host}}, "cookies": {}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="9host-site-content")
    ap.add_argument("--code", default="infra/cf-site-content.js")
    ap.add_argument("--mapped-host", default="jinks4.echo9.net")
    ap.add_argument("--unmapped-host", default="nope-zzz-ci.echo9.net")
    args = ap.parse_args()

    cf = boto3.client("cloudfront", region_name="us-east-1")
    name = args.name
    dev = cf.describe_function(Name=name, Stage="DEVELOPMENT")
    try:
        live_cfg = cf.describe_function(Name=name, Stage="LIVE")["FunctionSummary"]["FunctionConfig"]
        live_code = cf.get_function(Name=name, Stage="LIVE")["FunctionCode"].read()
    except cf.exceptions.NoSuchFunctionExists:
        live_cfg = live_code = None  # never published: nothing to restore

    failures = []
    try:
        with open(args.code, "rb") as f:
            code = f.read()
        etag = cf.update_function(Name=name, IfMatch=dev["ETag"], FunctionCode=code,
                                  FunctionConfig=dev["FunctionSummary"]["FunctionConfig"])["ETag"]
        for label, host, check in [
            ("mapped", args.mapped_host, lambda o: MAPPED_URI.match((o.get("request") or {}).get("uri", ""))),
            ("unmapped", args.unmapped_host, lambda o: (o.get("response") or {}).get("statusCode") == 404),
        ]:
            r = cf.test_function(Name=name, IfMatch=etag, Stage="DEVELOPMENT",
                                 EventObject=json.dumps(event(host)).encode())["TestResult"]
            err = r.get("FunctionErrorMessage")
            out = json.loads(r.get("FunctionOutput") or "{}")
            summary = (out.get("request") or {}).get("uri") or (out.get("response") or {}).get("statusCode")
            ok = not err and check(out)
            print(f"{label} {host}: {'OK' if ok else 'FAIL'} -> {summary} (compute {r.get('ComputeUtilization')})"
                  + (f" error={err}" if err else ""))
            if not ok:
                failures.append(label)
    finally:
        if live_code is not None:
            etag = cf.describe_function(Name=name, Stage="DEVELOPMENT")["ETag"]
            cf.update_function(Name=name, IfMatch=etag, FunctionCode=live_code, FunctionConfig=live_cfg)
            print("DEVELOPMENT stage restored to LIVE code")

    if failures:
        print(f"::error::CloudFront test-function failed for {name}: {', '.join(failures)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

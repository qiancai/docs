#!/usr/bin/env python3
"""TiDB Cloud API helper for doc e2e tests (Starter, v1beta1 serverless API).

Note: current runtime scope is TiDB Cloud Starter only (Essential/Premium/
Dedicated are out of scope per SKILL.md).

Spec source: idl repo, release/v1beta1 branch,
swagger/tidbcloud-oas-v1beta1-serverless.swagger.json
  host:     serverless.tidbapi.com
  basePath: /v1beta1
  GET    /clusters                 -> {"clusters": [...], "nextPageToken": "..."}
  DELETE /clusters/{clusterId}
  state enum: CREATING | ACTIVE | RESTORING | DELETED

Auth: HTTP Basic with API key pair
  TidbCloudPublicKey  as username
  TidbCloudPrivateKey as password

Usage:
  python3 api_orchestrator.py --instance docs-e2e-001 --wait-for
  python3 api_orchestrator.py --instance-id <clusterId> --delete
  python3 api_orchestrator.py --sql HOST USER --sql-file case.sql
  --dry-run prints actions without any side effect (covers API AND SQL).

Cleanup rule: prefer --instance-id recorded at creation time over name lookup.
Deletion is verified by polling until the cluster reaches DELETED or returns
404; otherwise cleanup status is reported as unknown, never assumed ok.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "https://serverless.tidbapi.com/v1beta1"


def auth_header(public_key, private_key):
    token = base64.b64encode(f"{public_key}:{private_key}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def api_call(method, url, headers, body=None, dry_run=False):
    if dry_run:
        print(f"[DRY-RUN] {method} {url}")
        return {}
    req = urllib.request.Request(url, method=method, headers=headers,
                                 data=body.encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"API error {e.code} on {method} {url}: {e.read().decode()}")


def list_clusters(headers, dry_run):
    """GET /clusters with pagination (nextPageToken) — name lookups must see
    every page, not just the first."""
    clusters, token = [], None
    while True:
        url = f"{BASE_URL}/clusters" + (f"?pageToken={token}" if token else "")
        data = api_call("GET", url, headers, dry_run=dry_run)
        clusters.extend(data.get("clusters", []))
        token = data.get("nextPageToken")
        if not token or dry_run:
            break
    return clusters


def wait_for_cluster(name, headers, dry_run=False, timeout=300):
    print(f"Waiting for cluster '{name}' to become ACTIVE (timeout {timeout}s)...")
    if dry_run:
        print("[DRY-RUN] would poll GET /clusters every 10s until state == ACTIVE")
        return {"clusterId": "dryrun-id", "displayName": name, "state": "ACTIVE"}
    start = time.time()
    while time.time() - start < timeout:
        for c in list_clusters(headers, dry_run):
            if c.get("displayName") == name or c.get("clusterId") == name:
                state = c.get("state", "UNKNOWN")
                print(f"  state = {state}")
                if state == "ACTIVE":
                    return c
        time.sleep(10)
    raise TimeoutError(f"Cluster {name} did not become ACTIVE within {timeout}s")


def delete_cluster(cluster_id, headers, dry_run=False, timeout=180):
    api_call("DELETE", f"{BASE_URL}/clusters/{cluster_id}", headers, dry_run=dry_run)
    print(f"{'[DRY-RUN] would delete' if dry_run else 'DELETE issued for'} cluster {cluster_id}")
    if dry_run:
        print("[DRY-RUN] would poll GET until state == DELETED or 404")
        return "unknown"
    # verify deletion completes; never assume ok without observing a terminal state
    start = time.time()
    while time.time() - start < timeout:
        try:
            c = api_call("GET", f"{BASE_URL}/clusters/{cluster_id}", headers)
            state = c.get("state", "UNKNOWN")
            print(f"  cleanup poll: state = {state}")
            if state == "DELETED":
                print(f"Deleted cluster {cluster_id} (verified)")
                return "ok"
        except SystemExit as e:
            if "404" in str(e):
                print(f"Deleted cluster {cluster_id} (verified: 404)")
                return "ok"
            raise
        time.sleep(10)
    print(f"WARNING: deletion of {cluster_id} not confirmed within {timeout}s — cleanup status unknown")
    return "unknown"


def run_sql(host, user, password, sql, dry_run=False):
    if dry_run:
        print(f"[DRY-RUN] would execute on {host} as {user}:\n{sql}")
        return ""
    env = dict(os.environ)
    if password:
        env["MYSQL_PWD"] = password
    cmd = ["mysql", "-h", host, "-P", "4000", "-u", user,
           "--ssl-mode=REQUIRED", "--batch", "--raw", "-e", sql]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    if p.returncode != 0:
        raise SystemExit(f"SQL failed: {p.stderr}")
    return p.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", help="displayName for --wait-for / name-based delete fallback")
    ap.add_argument("--instance-id", help="clusterId recorded at creation time (preferred for --delete)")
    ap.add_argument("--wait-for", action="store_true")
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--sql", nargs=2, metavar=("HOST", "USER"), help="run SQL_FILE via stdin path arg")
    ap.add_argument("--sql-file", help="path to a .sql file to execute with --sql")
    ap.add_argument("--dry-run", action="store_true", help="no side effects at all (API and SQL)")
    args = ap.parse_args()

    headers = None
    if not args.dry_run or args.wait_for or args.delete:
        pub = os.environ.get("TidbCloudPublicKey")
        priv = os.environ.get("TidbCloudPrivateKey")
        if not args.dry_run and (not pub or not priv):
            print("Error: set TidbCloudPublicKey and TidbCloudPrivateKey", file=sys.stderr)
            sys.exit(1)
        headers = auth_header(pub or "dry", priv or "dry")

    created_or_found = None
    if args.wait_for:
        if not args.instance:
            ap.error("--wait-for requires --instance")
        created_or_found = wait_for_cluster(args.instance, headers, args.dry_run)
        print("Cluster ready:", created_or_found.get("clusterId"),
              created_or_found.get("displayName"), created_or_found.get("state"))

    if args.delete:
        cid = args.instance_id
        if not cid and args.instance:
            clusters = list_clusters(headers, args.dry_run)
            target = next((c for c in clusters if c.get("displayName") == args.instance), None)
            if not target and not args.dry_run:
                print(f"No cluster named {args.instance} to delete")
                return
            cid = target["clusterId"] if target else "dryrun-id"
        if not cid:
            ap.error("--delete requires --instance-id (preferred) or --instance")
        delete_cluster(cid, headers, args.dry_run)

    if args.sql:
        host, user = args.sql
        sql = open(args.sql_file, encoding="utf-8").read() if args.sql_file else sys.stdin.read()
        out = run_sql(host, user, os.environ.get("MYSQL_PWD"), sql, args.dry_run)
        if not args.dry_run:
            print(out)


if __name__ == "__main__":
    main()

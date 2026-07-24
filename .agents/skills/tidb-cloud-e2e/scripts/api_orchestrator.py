#!/usr/bin/env python3
"""TiDB Cloud API helper for the W2 web-agent pilot.

Usage:
  export TidbCloudPublicKey=...
  export TidbCloudPrivateKey=...
  python3 api_orchestrator.py --project-id <id> --instance docs-w2-pilot-001 --region us-west-2 --provider AWS

Modes:
  --wait-for     poll until the named Starter cluster is AVAILABLE
  --delete       delete the named Starter cluster
  --sql HOST PASSWORD   run the quickstart SQL block and assert 3 rows
  --dry-run      print actions without calling the API
"""
import argparse
import base64
import os
import sys
import time
import urllib.request
import urllib.error
import json

SQL_BLOCK = """use test;

-- create a new table t with id and name
CREATE TABLE
  `t` (`id` INT, `name` VARCHAR(255));

-- add 3 rows
INSERT INTO
  `t` (`id`, `name`)
VALUES
  (1, 'row1'),
  (2, 'row2'),
  (3, 'row3');

-- query all
SELECT
  `id`,
  `name`
FROM
  `t`;"""


def auth_header(public_key, private_key):
    token = base64.b64encode(f"{public_key}:{private_key}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def api_call(method, url, headers, body=None, dry_run=False):
    if dry_run:
        print(f"[DRY-RUN] {method} {url}")
        if body:
            print(f"[DRY-RUN] body: {body}")
        return {}
    req = urllib.request.Request(url, method=method, headers=headers, data=body.encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise SystemExit(f"API error {e.code}: {err}")


def list_clusters(base_url, project_id, headers, dry_run):
    url = f"{base_url}/v1beta/projects/{project_id}/clusters"
    data = api_call("GET", url, headers, dry_run=dry_run)
    return data.get("clusters", [])


def wait_for_cluster(base_url, project_id, name, headers, dry_run=False, timeout=300):
    print(f"Waiting for cluster '{name}' to become AVAILABLE (timeout {timeout}s)...")
    if dry_run:
        print("[DRY-RUN] would poll every 10s until AVAILABLE")
        return {"clusterId": "dryrun-id", "displayName": name, "status": {"clusterStatus": "AVAILABLE"}}
    start = time.time()
    while time.time() - start < timeout:
        clusters = list_clusters(base_url, project_id, headers, dry_run)
        for c in clusters:
            if c.get("displayName") == name or c.get("clusterId") == name:
                state = c.get("status", {}).get("clusterStatus", "UNKNOWN")
                print(f"  state = {state}")
                if state == "AVAILABLE":
                    return c
        time.sleep(10)
    raise TimeoutError(f"Cluster {name} did not become AVAILABLE within {timeout}s")


def delete_cluster(base_url, project_id, cluster_id, headers, dry_run=False):
    url = f"{base_url}/v1beta/projects/{project_id}/clusters/{cluster_id}"
    api_call("DELETE", url, headers, dry_run=dry_run)
    print(f"Deleted cluster {cluster_id}")


def run_sql(host, password, sql):
    import subprocess
    cmd = ["/opt/homebrew/opt/mysql-client@8.0/bin/mysql",
           "-h", host, "-P", "4000", "-uroot", "-p" + password,
           "--batch", "--raw", "-e", sql]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise SystemExit(f"SQL failed: {p.stderr}")
    return p.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--instance", default="docs-w2-pilot-test")
    ap.add_argument("--region", default="us-west-2")
    ap.add_argument("--provider", default="AWS")
    ap.add_argument("--base-url", default="https://api.tidbcloud.com")
    ap.add_argument("--wait-for", action="store_true")
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--sql", nargs=2, metavar=("HOST", "PASSWORD"), help="run the quickstart SQL block")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        headers = {"Authorization": "Basic DRYRUN", "Content-Type": "application/json"}
    else:
        pub = os.environ.get("TidbCloudPublicKey")
        priv = os.environ.get("TidbCloudPrivateKey")
        if not pub or not priv:
            print("Error: set TidbCloudPublicKey and TidbCloudPrivateKey environment variables", file=sys.stderr)
            sys.exit(1)
        headers = auth_header(pub, priv)

    if args.wait_for:
        c = wait_for_cluster(args.base_url, args.project_id, args.instance, headers, args.dry_run)
        print("Cluster ready:", c.get("clusterId"), c.get("displayName"), c.get("status"))

    if args.delete:
        clusters = list_clusters(args.base_url, args.project_id, headers, args.dry_run)
        target = next((c for c in clusters if c.get("displayName") == args.instance), None)
        if not target:
            print(f"No cluster named {args.instance} to delete")
            return
        delete_cluster(args.base_url, args.project_id, target["clusterId"], headers, args.dry_run)

    if args.sql:
        out = run_sql(args.sql[0], args.sql[1], SQL_BLOCK)
        print(out)
        # weak assertion: output contains 3 data rows with row1,row2,row3
        if "row1" in out and "row2" in out and "row3" in out:
            print("SQL assertion PASSED")
        else:
            print("SQL assertion FAILED")
            sys.exit(1)


if __name__ == "__main__":
    main()

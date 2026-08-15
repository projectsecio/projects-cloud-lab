#!/usr/bin/env python3
"""
configure_lab.py — fill in student-specific values for the ProjectX cloud lab.

It copies the lab templates (iam/, portal/, s3-seed/, deploy/) into a fresh
./build/ directory and substitutes the values that differ per student:

  * data S3 bucket name        (default: projectx-portal-lab)
  * code S3 bucket name        (default: <data-bucket>-code)
  * AWS account ID             (replaces the <ACCOUNT_ID> placeholder)
  * lab-attacker access key ID + secret  (into backup/aws_dev_credentials.txt)
  * AWS region                 (default: us-east-1)

The tracked template files are never modified, so no secrets end up in git.
Upload everything from build/ instead of the originals.

Interactive by default — just run it and answer the prompts (press Enter to
accept a shown [default]):

  python configure_lab.py

Any value can also be supplied as a flag to skip its prompt (handy for scripting):

  python configure_lab.py \
      --account-id 123456789012 \
      --data-bucket projectx-portal-lab \
      --code-bucket projectx-portal-lab-code \
      --region us-east-1 \
      --access-key-id AKIA... \
      --secret-access-key ...        # omit to be prompted securely

Run it from anywhere; paths are resolved relative to this script.
"""
from __future__ import annotations

import argparse
import getpass
import re
import shutil
import sys
from pathlib import Path

# projects/cloud-lab/  (this file lives in deploy/)
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
SRC_DIRS = ["iam", "portal", "s3-seed", "deploy"]
CRED_FILE = Path("s3-seed") / "backup" / "aws_dev_credentials.txt"

# Default strings that appear in the templates and get replaced.
DEFAULT_DATA_BUCKET = "projectx-portal-lab"
DEFAULT_CODE_BUCKET = "projectx-portal-lab-code"
DEFAULT_REGION = "us-east-1"
PLACEHOLDER_ACCOUNT = "<ACCOUNT_ID>"

# Files that are text and safe to rewrite (everything we ship is text).
TEXT_SUFFIXES = {".json", ".py", ".sh", ".txt", ".service", ".html", ".cfg", ".md", ""}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Configure the ProjectX cloud lab for a student.")
    p.add_argument("--account-id", help="12-digit AWS account ID")
    p.add_argument("--data-bucket", help=f"portal data bucket name (default: {DEFAULT_DATA_BUCKET})")
    p.add_argument("--code-bucket", help="app code bucket name (default: <data-bucket>-code)")
    p.add_argument("--region", help=f"AWS region (default: {DEFAULT_REGION})")
    p.add_argument("--access-key-id", help="lab-attacker access key ID")
    p.add_argument("--secret-access-key", help="lab-attacker secret (omit to be prompted)")
    p.add_argument("--force", action="store_true", help="overwrite an existing build/ directory")
    return p.parse_args()


def prompt(label: str, default: str | None = None, secret: bool = False) -> str:
    """Interactively ask for a value. Enter accepts the [default] if one exists."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        try:
            raw = (getpass.getpass if secret else input)(f"{label}{suffix}: ")
        except EOFError:
            if default is not None:
                return default
            sys.exit(f"\nerror: {label} is required "
                     "(no interactive input available; pass its --flag instead).")
        value = raw.strip()
        if value:
            return value
        if default is not None:
            return default
        print("  A value is required.")


def gather(args: argparse.Namespace) -> dict[str, str]:
    # Anything not supplied via a flag is asked for interactively. Required
    # values (account ID, keys) have no default and must be entered.
    supplied = [args.account_id, args.data_bucket, args.code_bucket,
                args.region, args.access_key_id, args.secret_access_key]
    if not all(supplied):
        print("Configure the ProjectX cloud lab - press Enter to accept [defaults].\n")

    account_id = args.account_id or prompt("AWS account ID (12 digits)")
    data_bucket = args.data_bucket or prompt("Data bucket name", DEFAULT_DATA_BUCKET)
    code_bucket = args.code_bucket or prompt("Code bucket name", f"{data_bucket}-code")
    region = args.region or prompt("AWS region", DEFAULT_REGION)
    access_key_id = args.access_key_id or prompt("lab-attacker access key ID")
    secret = args.secret_access_key or prompt("lab-attacker secret access key", secret=True)

    if not re.fullmatch(r"\d{12}", account_id):
        sys.exit(f"error: account ID must be 12 digits, got: {account_id!r}")
    if not access_key_id.startswith(("AKIA", "ASIA")):
        print(f"  warning: access key ID {access_key_id!r} does not look like an AWS key")

    return {
        "account_id": account_id,
        "data_bucket": data_bucket,
        "code_bucket": code_bucket,
        "region": region,
        "access_key_id": access_key_id,
        "secret": secret,
    }


def substitute(text: str, cfg: dict[str, str]) -> str:
    # Order matters: replace the longer code-bucket name before the data-bucket
    # name, otherwise "projectx-portal-lab" would corrupt "...-lab-code".
    text = text.replace(DEFAULT_CODE_BUCKET, cfg["code_bucket"])
    text = text.replace(DEFAULT_DATA_BUCKET, cfg["data_bucket"])
    text = text.replace(PLACEHOLDER_ACCOUNT, cfg["account_id"])
    text = text.replace(DEFAULT_REGION, cfg["region"])
    return text


def fill_credentials(text: str, cfg: dict[str, str]) -> str:
    text = re.sub(r"(?m)^aws_access_key_id\s*=.*$",
                  f"aws_access_key_id = {cfg['access_key_id']}", text)
    text = re.sub(r"(?m)^aws_secret_access_key\s*=.*$",
                  f"aws_secret_access_key = {cfg['secret']}", text)
    text = re.sub(r"(?m)^region\s*=.*$", f"region = {cfg['region']}", text)
    return text


def main() -> None:
    args = parse_args()

    if BUILD.exists():
        if not args.force:
            sys.exit(f"error: {BUILD} already exists. Re-run with --force to overwrite.")
        shutil.rmtree(BUILD)

    cfg = gather(args)

    BUILD.mkdir(parents=True)
    for name in SRC_DIRS:
        src = ROOT / name
        if src.exists():
            shutil.copytree(src, BUILD / name)

    changed = 0
    for path in BUILD.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # skip anything non-text
        updated = substitute(original, cfg)
        rel = path.relative_to(BUILD)
        if rel == CRED_FILE:
            updated = fill_credentials(updated, cfg)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1

    masked = cfg["access_key_id"][:4] + "..." + cfg["access_key_id"][-4:]
    print("\nProjectX lab configured ->", BUILD)
    print(f"  data bucket : {cfg['data_bucket']}")
    print(f"  code bucket : {cfg['code_bucket']}")
    print(f"  account id  : {cfg['account_id']}")
    print(f"  region      : {cfg['region']}")
    print(f"  access key  : {masked}   (secret written, not shown)")
    print(f"  files updated: {changed}")
    print("\nNext steps (from the build/ directory):")
    print(f"  aws s3 mb s3://{cfg['data_bucket']} --region {cfg['region']}")
    print(f"  aws s3 mb s3://{cfg['code_bucket']} --region {cfg['region']}")
    print(f"  aws s3 sync build/s3-seed/ s3://{cfg['data_bucket']}/")
    print(f"  aws s3 sync build/portal/  s3://{cfg['code_bucket']}/portal/")
    print("  # then apply build/iam/*.json and launch EC2 with build/deploy/user-data.sh")
    print("\nNote: build/ contains real credentials - do NOT commit it (see .gitignore).")


if __name__ == "__main__":
    main()

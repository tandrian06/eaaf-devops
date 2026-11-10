import argparse
import json
import os
import sys
from pathlib import Path

import httpx
import yaml
from dotenv import dotenv_values
from pydantic import ValidationError

from eaaf_devops.architecture import Architecture, review
from eaaf_devops.intake import IntakeError, draft_architecture
from eaaf_devops.terraform import write_terraform

EXIT_BY_STATUS = {"ready_for_review": 0, "needs_input": 2, "unsupported": 3}


def main() -> int:
    parser = argparse.ArgumentParser(description="Review an EAAF DevOps architecture manifest.")
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("manifest", type=Path, nargs="?")
    command.add_argument("--schema", action="store_true", help="Print the version 1 JSON Schema.")
    command.add_argument("--describe", type=Path, metavar="FILE", help="Draft a manifest from a UTF-8 description.")
    parser.add_argument("--terraform", type=Path, metavar="OUTPUT.tf", help="Generate Terraform from a YAML manifest.")
    args = parser.parse_args()
    if args.terraform and (not args.manifest or args.terraform.suffix != ".tf"):
        parser.error("--terraform requires a YAML manifest and a .tf output path")
    if args.schema:
        print(json.dumps(Architecture.model_json_schema(), indent=2))
        return 0

    try:
        if args.describe:
            local = dotenv_values(Path.cwd() / ".env")
            key = os.getenv("EAAF_DEVOPS_API_KEY", local.get("EAAF_DEVOPS_API_KEY"))
            if not key:
                raise IntakeError("Set EAAF_DEVOPS_API_KEY before requesting a draft.")
            url = os.getenv("EAAF_GATEWAY_URL", local.get("EAAF_GATEWAY_URL") or "http://127.0.0.1:8000")
            with httpx.Client(base_url=url, timeout=20, trust_env=False) as client:
                manifest = draft_architecture(client, args.describe.read_text(encoding="utf-8"), key)
        else:
            manifest = Architecture.model_validate(yaml.safe_load(args.manifest.read_text(encoding="utf-8")))
    except IntakeError as exc:
        print(f"Architecture draft unavailable: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError, httpx.InvalidURL) as exc:
        print(f"Invalid architecture manifest: {exc}", file=sys.stderr)
        return 1

    result = review(manifest)
    if args.terraform and result.manifest.status == "ready_for_review":
        try:
            write_terraform(result, args.terraform)
        except OSError as exc:
            print(f"Could not write Terraform: {exc}", file=sys.stderr)
            return 1
    print(yaml.safe_dump(result.model_dump(mode="json"), sort_keys=False), end="")
    return EXIT_BY_STATUS[result.manifest.status]


if __name__ == "__main__":
    raise SystemExit(main())

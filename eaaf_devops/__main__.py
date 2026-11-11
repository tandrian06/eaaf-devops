import argparse
import json
import os
import sys
from pathlib import Path

import httpx
import yaml
from dotenv import dotenv_values

from eaaf_devops.architecture import Architecture, review
from eaaf_devops.container_demo import ContainerDemo, draft_container
from eaaf_devops.module_contract import GIT_SOURCE, draft_module, inspect_module, write_module_files
from eaaf_devops.intake import IntakeError, draft_architecture
from eaaf_devops.terraform import write_terraform

EXIT_BY_STATUS = {"ready_for_review": 0, "needs_input": 2, "unsupported": 3}


def main() -> int:
    parser = argparse.ArgumentParser(description="Review an EAAF DevOps architecture manifest.")
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("manifest", type=Path, nargs="?")
    command.add_argument("--schema", action="store_true", help="Print the version 1 JSON Schema.")
    command.add_argument("--describe", type=Path, metavar="FILE", help="Draft a manifest from a UTF-8 description.")
    command.add_argument("--describe-demo", type=Path, metavar="FILE", help="Draft inputs for a single Fargate container.")
    command.add_argument("--demo", type=Path, metavar="YAML", help="Read reviewed container demo inputs.")
    parser.add_argument("--terraform", type=Path, metavar="OUTPUT.tf", help="Generate Terraform from a YAML manifest.")
    parser.add_argument("--output", type=Path, metavar="DIRECTORY", help="Write the demo module call and tfvars.")
    parser.add_argument("--module-source", help="Terraform module directory or GitHub source pinned to a full commit SHA.")
    parser.add_argument("--module-dir", type=Path, help="Local checkout of the module for a pinned GitHub source.")
    args = parser.parse_args()
    if args.terraform and (not args.manifest or args.terraform.suffix != ".tf"):
        parser.error("--terraform requires a YAML manifest and a .tf output path")
    if args.output and not args.demo:
        parser.error("--output requires --demo")
    if args.output and not args.module_source:
        parser.error("--output requires --module-source")
    if args.module_source and not (args.demo or args.describe_demo):
        parser.error("--module-source requires --demo or --describe-demo")
    remote_module = bool(args.module_source and GIT_SOURCE.fullmatch(args.module_source))
    if remote_module != bool(args.module_dir):
        parser.error("A pinned GitHub source requires --module-dir pointing to the same module revision")
    if args.schema:
        print(json.dumps(Architecture.model_json_schema(), indent=2))
        return 0

    try:
        contract = None
        if args.module_source:
            module_dir = args.module_dir if remote_module else Path(args.module_source)
            contract = inspect_module(module_dir)
        if args.describe or args.describe_demo:
            local = dotenv_values(Path.cwd() / ".env")
            key = os.getenv("EAAF_DEVOPS_API_KEY", local.get("EAAF_DEVOPS_API_KEY"))
            if not key:
                raise IntakeError("Set EAAF_DEVOPS_API_KEY before requesting a draft.")
            url = os.getenv("EAAF_GATEWAY_URL", local.get("EAAF_GATEWAY_URL") or "http://127.0.0.1:8000")
            description = (args.describe or args.describe_demo).read_text(encoding="utf-8")
            with httpx.Client(base_url=url, timeout=20, trust_env=False) as client:
                if args.describe_demo and contract is not None:
                    values = draft_module(client, description, key, contract)
                elif args.describe_demo:
                    demo = draft_container(client, description, key)
                else:
                    manifest = draft_architecture(client, description, key)
        elif args.demo:
            data = yaml.safe_load(args.demo.read_text(encoding="utf-8"))
            if contract is None:
                demo = ContainerDemo.model_validate(data)
            else:
                values = contract.check(data)
        else:
            manifest = Architecture.model_validate(yaml.safe_load(args.manifest.read_text(encoding="utf-8")))
    except IntakeError as exc:
        print(f"Architecture draft unavailable: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, yaml.YAMLError, httpx.InvalidURL) as exc:
        print(f"Invalid architecture manifest: {exc}", file=sys.stderr)
        return 1

    if args.demo or args.describe_demo:
        if contract is None:
            values = demo.model_dump()
            missing = demo.open_decisions
        else:
            missing = contract.missing(values)
        print(yaml.safe_dump(values, sort_keys=False), end="")
        if missing:
            print(f"Missing inputs: {', '.join(missing)}", file=sys.stderr)
            return 2
        if args.output:
            try:
                write_module_files(contract, values, args.output, args.module_source)
            except (OSError, ValueError) as exc:
                print(f"Could not write Terraform: {exc}", file=sys.stderr)
                return 1
        return 0

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

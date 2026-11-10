import argparse
import json
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from eaaf_devops.architecture import Architecture, review

EXIT_BY_STATUS = {"ready_for_review": 0, "needs_input": 2, "unsupported": 3}


def main() -> int:
    parser = argparse.ArgumentParser(description="Review an EAAF DevOps architecture manifest.")
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("manifest", type=Path, nargs="?")
    command.add_argument("--schema", action="store_true", help="Print the version 1 JSON Schema.")
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(Architecture.model_json_schema(), indent=2))
        return 0

    try:
        manifest = Architecture.model_validate(yaml.safe_load(args.manifest.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError) as exc:
        print(f"Invalid architecture manifest: {exc}", file=sys.stderr)
        return 1

    result = review(manifest)
    print(yaml.safe_dump(result.model_dump(mode="json"), sort_keys=False), end="")
    return EXIT_BY_STATUS[result.manifest.status]


if __name__ == "__main__":
    raise SystemExit(main())

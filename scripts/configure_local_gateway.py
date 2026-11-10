import argparse
from pathlib import Path
from secrets import token_urlsafe

import yaml
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare local EAAF Core configuration for DevOps.")
    parser.add_argument("core", type=Path, help="Path to the EAAF Core checkout.")
    args = parser.parse_args()

    core = args.core.resolve()
    base = yaml.safe_load((core / "config" / "applications.yaml").read_text(encoding="utf-8"))
    if "devops" in base["applications"]:
        parser.error("The Core config already contains a devops profile.")
    base["applications"]["devops"] = {
        "domain": "Platform Engineering",
        "cost_center": "DEMO-DEVOPS",
        "key_env": "EAAF_DEVOPS_API_KEY",
        "allowed_models": ["eaaf-devops-architecture"],
        "requests_per_day": 20,
        "monthly_budget_cents": 100,
        "request_cost_cents": 2,
    }
    local = ROOT / ".eaaf-local"
    local.mkdir(exist_ok=True)
    policies = local / "applications.yaml"
    policies.write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")

    env_file = ROOT / ".env"
    if not dotenv_values(env_file).get("EAAF_DEVOPS_API_KEY"):
        set_key(env_file, "EAAF_DEVOPS_API_KEY", token_urlsafe(32))
    set_key(env_file, "EAAF_DEVOPS_ROOT", ROOT.as_posix())
    set_key(env_file, "EAAF_DEVOPS_POLICIES", policies.as_posix())
    print("Prepared the local DevOps identity and policy overlay.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

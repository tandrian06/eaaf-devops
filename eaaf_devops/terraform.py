import json
from pathlib import Path

from eaaf_devops.architecture import Review


def write_terraform(result: Review, destination: Path) -> None:
    manifest = result.manifest
    if manifest.status != "ready_for_review":
        raise ValueError("Terraform generation requires a ready_for_review manifest.")

    values = {
        "region": manifest.aws.region,
        "vpc_id": manifest.aws.vpc_id,
        "container_port": manifest.application.container_port,
        "image": manifest.application.image_uri,
        "internal": manifest.ingress.visibility == "internal",
        "certificate_arn": manifest.ingress.certificate_arn,
        "domain_name": manifest.ingress.domain_name,
        "task_subnet_ids": sorted(set(manifest.runtime.private_subnet_ids)),
        "outbound_access": manifest.runtime.outbound_access,
    }
    width = max(map(len, values))
    bindings = []
    for key, value in values.items():
        literal = json.dumps(value, ensure_ascii=False).replace("${", "$${").replace("%{", "%%{")
        bindings.append(f"  {key:<{width}} = {literal}")

    template = Path(__file__).with_name("templates") / "aws-ecs-fargate-web-v1.tf"
    content = template.read_text(encoding="utf-8").replace("  # EAAF_MANIFEST", "\n".join(bindings), 1)
    with destination.open("x", encoding="utf-8", newline="\n") as output:
        output.write(content)

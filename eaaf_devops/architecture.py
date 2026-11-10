import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PATTERN = "aws-ecs-fargate-web"
Status = Literal["ready_for_review", "needs_input", "unsupported"]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Region = Annotated[str, StringConstraints(pattern=r"^[a-z]{2}(?:-[a-z0-9]+)+-[0-9]+$")]
VpcId = Annotated[str, StringConstraints(pattern=r"^vpc-[0-9a-f]{8}(?:[0-9a-f]{9})?$")]
SubnetId = Annotated[str, StringConstraints(pattern=r"^subnet-[0-9a-f]{8}(?:[0-9a-f]{9})?$")]
ECR_IMAGE = re.compile(
    r"(?P<account>[0-9]{12})\.dkr\.ecr\.(?P<region>[a-z0-9-]+)\.amazonaws\.com/"
    r"[a-z0-9][a-z0-9._/-]*(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|@sha256:[0-9a-f]{64})"
)
ACM_CERTIFICATE = re.compile(
    r"arn:aws:acm:(?P<region>[a-z0-9-]+):(?P<account>[0-9]{12}):certificate/"
    r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
)


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Application(Section):
    container_port: int | None = Field(default=None, ge=1, le=65535)
    image_uri: NonEmpty | None = None
    stateless: bool | None = None


class AWS(Section):
    region: Region | None = None
    vpc_id: VpcId | None = None


class Ingress(Section):
    protocol: Literal["HTTP", "HTTPS"] = "HTTPS"
    visibility: Literal["public", "internal"] | None = None
    domain_name: NonEmpty | None = None
    certificate_arn: NonEmpty | None = None


class Runtime(Section):
    platform: NonEmpty = "ecs-fargate"
    public_ip: bool = False
    private_subnet_ids: list[SubnetId] = Field(default_factory=list)
    outbound_access: Literal["nat", "vpc-endpoints"] | None = None


class Architecture(Section):
    schema_version: Literal[1]
    pattern: NonEmpty
    status: Status | None = None
    application: Application = Field(default_factory=Application)
    aws: AWS = Field(default_factory=AWS)
    ingress: Ingress = Field(default_factory=Ingress)
    runtime: Runtime = Field(default_factory=Runtime)


class Review(Section):
    manifest: Architecture
    open_decisions: list[str]
    pattern_conflicts: list[str]


def review(manifest: Architecture) -> Review:
    application, aws, ingress, runtime = (
        manifest.application, manifest.aws, manifest.ingress, manifest.runtime
    )
    missing = []
    for value, field in (
        (application.container_port, "application.container_port"),
        (application.image_uri, "application.image_uri"),
        (application.stateless, "application.stateless"),
        (aws.region, "aws.region"),
        (aws.vpc_id, "aws.vpc_id"),
        (ingress.visibility, "ingress.visibility"),
        (ingress.domain_name, "ingress.domain_name"),
        (ingress.certificate_arn, "ingress.certificate_arn"),
        (runtime.outbound_access, "runtime.outbound_access"),
    ):
        if value is None:
            missing.append(field)
    if len(set(runtime.private_subnet_ids)) < 2:
        missing.append("runtime.private_subnet_ids (two distinct IDs required)")

    conflicts = []
    for incompatible, reason in (
        (manifest.pattern != PATTERN, f"Only {PATTERN} is supported."),
        (application.stateless is False, "Persistent application state is outside this pattern."),
        (ingress.protocol != "HTTPS", "The application listener requires HTTPS."),
        (runtime.platform != "ecs-fargate", "The pattern requires ECS Fargate."),
        (runtime.public_ip, "Fargate tasks must not have public IP addresses."),
    ):
        if incompatible:
            conflicts.append(reason)

    if application.image_uri is not None:
        image = ECR_IMAGE.fullmatch(application.image_uri)
        if image is None:
            conflicts.append("The image must be a tagged or digest-pinned private ECR URI.")
        elif aws.region and image["region"] != aws.region:
            conflicts.append("This pattern expects the ECR image in the workload region.")

    if ingress.certificate_arn is not None:
        certificate = ACM_CERTIFICATE.fullmatch(ingress.certificate_arn)
        if certificate is None:
            conflicts.append("The HTTPS listener requires an ACM certificate ARN.")
        elif aws.region and certificate["region"] != aws.region:
            conflicts.append("The ACM certificate must be in the workload region.")

    if conflicts:
        status = "unsupported"
    elif missing:
        status = "needs_input"
    else:
        status = "ready_for_review"

    return Review(
        manifest=manifest.model_copy(update={"status": status}),
        open_decisions=missing,
        pattern_conflicts=conflicts,
    )

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from eaaf_devops.architecture import Architecture, review

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def example(name):
    return yaml.safe_load((EXAMPLES / f"{name}.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name, expected", [
    ("complete", "ready_for_review"),
    ("incomplete", "needs_input"),
    ("outside-pattern", "unsupported"),
])
def test_example_status(name, expected):
    result = review(Architecture.model_validate(example(name)))
    assert result.manifest.status == expected


def test_incomplete_manifest_keeps_unknowns_and_reports_them():
    result = review(Architecture.model_validate(example("incomplete")))
    assert result.manifest.aws.region is None
    assert result.manifest.ingress.visibility is None
    assert "aws.region" in result.open_decisions
    assert "ingress.visibility" in result.open_decisions
    assert "application.stateless" in result.open_decisions
    assert "application.container_port" not in result.open_decisions


def test_status_is_derived_and_does_not_override_pattern_conflicts():
    source = example("outside-pattern")
    source["status"] = "ready_for_review"
    result = review(Architecture.model_validate(source))
    assert result.manifest.status == "unsupported"
    assert result.pattern_conflicts == ["Persistent application state is outside this pattern."]


def test_two_distinct_subnets_are_required():
    source = example("complete")
    source["runtime"]["private_subnet_ids"] = ["subnet-0123456789abcdef0"] * 2
    result = review(Architecture.model_validate(source))
    assert result.manifest.status == "needs_input"
    assert any("private_subnet_ids" in field for field in result.open_decisions)


def test_rejects_public_task_ips_and_a_cross_region_certificate():
    source = example("complete")
    source["runtime"]["public_ip"] = True
    source["ingress"]["certificate_arn"] = source["ingress"]["certificate_arn"].replace("eu-west-3", "eu-west-1")
    result = review(Architecture.model_validate(source))
    assert result.manifest.status == "unsupported"
    assert len(result.pattern_conflicts) == 2


@pytest.mark.parametrize("port", [0, 65536, "8080", True])
def test_rejects_invalid_container_ports(port):
    source = example("complete")
    source["application"]["container_port"] = port
    with pytest.raises(ValidationError, match="container_port"):
        Architecture.model_validate(source)

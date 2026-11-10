from pathlib import Path

import pytest
import yaml

from eaaf_devops.__main__ import main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_generates_pinned_modules_without_overwriting(monkeypatch, tmp_path):
    destination = tmp_path / "main.tf"
    monkeypatch.setattr("sys.argv", ["eaaf_devops", str(EXAMPLES / "complete.yaml"), "--terraform", str(destination)])
    assert main() == 0
    content = destination.read_text(encoding="utf-8")
    assert 'source  = "terraform-aws-modules/alb/aws"' in content
    assert 'version = "9.17.0"' in content
    assert 'source  = "terraform-aws-modules/ecs/aws//modules/service"' in content
    assert 'version = "6.0.0"' in content
    assert 'assign_public_ip = false' in content
    assert '123456789012.dkr.ecr.eu-west-3.amazonaws.com/demo-api:1.0.0' in content
    assert main() == 1
    assert destination.read_text(encoding="utf-8") == content


@pytest.mark.parametrize(("example", "exit_code"), [("incomplete", 2), ("outside-pattern", 3)])
def test_never_generates_for_unreviewable_manifest(monkeypatch, tmp_path, example, exit_code):
    destination = tmp_path / "main.tf"
    monkeypatch.setattr("sys.argv", ["eaaf_devops", str(EXAMPLES / f"{example}.yaml"), "--terraform", str(destination)])
    assert main() == exit_code
    assert not destination.exists()


def test_manifest_strings_cannot_inject_terraform_expressions(monkeypatch, tmp_path):
    manifest = yaml.safe_load((EXAMPLES / "complete.yaml").read_text(encoding="utf-8"))
    manifest["ingress"]["domain_name"] = '${file("secrets")} %{if true}'
    source = tmp_path / "manifest.yaml"
    source.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    destination = tmp_path / "main.tf"
    monkeypatch.setattr("sys.argv", ["eaaf_devops", str(source), "--terraform", str(destination)])
    assert main() == 0
    content = destination.read_text(encoding="utf-8")
    assert "$${file(" in content
    assert "%%{if true}" in content

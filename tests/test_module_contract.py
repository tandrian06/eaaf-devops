import json

import httpx
import pytest

from eaaf_devops.module_contract import draft_module, inspect_module, write_module_files


def test_generation_follows_the_module_contract(tmp_path):
    module = tmp_path / "prepared-module"
    module.mkdir()
    (module / "variables.tf").write_text(
        'variable "name" { type = string }\n'
        'variable "settings" { type = object({ port = number }) }\n'
        'variable "replicas" {\n  type = number\n  default = 1\n}\n',
        encoding="utf-8",
    )
    (module / "outputs.tf").write_text('output "workload" { value = var.name }\n', encoding="utf-8")
    contract = inspect_module(module)
    values = {"region": "eu-north-1", "name": "web", "settings": {"port": 80}}
    target = tmp_path / "output"

    write_module_files(contract, values, target, str(module))

    config = (target / "main.tf").read_text(encoding="utf-8")
    assert 'source = "../prepared-module"' in config
    assert "type = object({ port = number })" in config
    assert "settings = var.settings" in config
    assert "replicas" not in config
    assert "module.demo.workload" in config
    assert json.loads((target / "terraform.tfvars.json").read_text()) == values

    with pytest.raises(ValueError, match="Missing inputs: settings"):
        write_module_files(contract, {"region": "eu-north-1", "name": "web"}, tmp_path / "bad", str(module))
    assert not (tmp_path / "bad").exists()


def test_description_uses_discovered_fields_and_omits_invented_values(tmp_path):
    (tmp_path / "variables.tf").write_text(
        'variable "listener_port" { type = number }\n'
        'variable "internal_name" { type = string }\n',
        encoding="utf-8",
    )
    contract = inspect_module(tmp_path)

    def gateway(request):
        prompt = json.loads(request.content)["messages"][0]["content"]
        assert "listener_port" in prompt
        assert "internal_name" in prompt
        draft = {"listener_port": 8080, "internal_name": "invented", "region": "eu-north-1"}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(draft)}}]})

    with httpx.Client(base_url="http://gateway.test", transport=httpx.MockTransport(gateway)) as client:
        values = draft_module(client, "Use port 8080 in eu-north-1.", "test-key", contract)

    assert values == {"listener_port": 8080, "region": "eu-north-1"}
    assert contract.missing(values) == ["internal_name"]

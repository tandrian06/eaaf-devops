import json

import httpx

from eaaf_devops.container_demo import draft_container


def test_demo_intake_keeps_only_values_from_description():
    def gateway(request):
        body = json.loads(request.content)
        assert body["model"] == "eaaf-devops-architecture"
        result = {"container_port": 80, "subnet_id": "subnet-0123456789abcdef0"}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]})

    with httpx.Client(base_url="http://gateway.test", transport=httpx.MockTransport(gateway)) as client:
        demo = draft_container(client, "Run an HTTP container on port 80.", "test-key")

    assert demo.container_port == 80
    assert "subnet_id" in demo.open_decisions

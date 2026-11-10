import json

import httpx
import pytest

from eaaf_devops.architecture import review
from eaaf_devops.intake import IntakeError, draft_architecture


def test_draft_uses_gateway_and_discards_invented_resource_values():
    description = "Stateless container API on port 8080 with HTTPS."

    def gateway(request):
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-devops"
        body = json.loads(request.content)
        assert body["model"] == "eaaf-devops-architecture"
        assert body["messages"][-1] == {"role": "user", "content": description}
        payload = {
            "schema_version": 1,
            "pattern": "aws-ecs-fargate-web",
            "application": {"container_port": 8080, "stateless": True},
            "aws": {"region": "eu-west-3", "vpc_id": "vpc-0123456789abcdef0"},
            "ingress": {"domain_name": "api.example.com"},
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})

    with httpx.Client(base_url="http://gateway.test", transport=httpx.MockTransport(gateway)) as client:
        result = review(draft_architecture(client, description, "test-devops"))

    assert result.manifest.status == "needs_input"
    assert result.manifest.application.container_port == 8080
    assert result.manifest.aws.region is None
    assert result.manifest.aws.vpc_id is None
    assert result.manifest.ingress.domain_name is None


@pytest.mark.parametrize("response, message", [
    (httpx.Response(403, text="hidden upstream content"), "HTTP 403"),
    (httpx.Response(200, json={"choices": [{"message": {"content": "not JSON"}}]}), "valid architecture draft"),
])
def test_intake_sanitizes_gateway_errors(response, message):
    with httpx.Client(
        base_url="http://gateway.test", transport=httpx.MockTransport(lambda request: response)
    ) as client:
        with pytest.raises(IntakeError, match=message):
            draft_architecture(client, "A container API", "test-devops")

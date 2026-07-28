"""Nacos contract tests — mock mode (real server optional via env)."""

from __future__ import annotations

import os

import pytest

from workcopilot_expert_factory.publishers.nacos import NacosPublisher


@pytest.fixture
def publisher():
    mock = os.environ.get("WORKCOPILOT_NACOS_LIVE") != "1"
    return NacosPublisher(
        os.environ.get("NACOS_SERVER_URL", "http://127.0.0.1:8848/nacos"),
        namespace=os.environ.get("NACOS_NAMESPACE", "workcopilot-test"),
        mock=mock,
    )


def test_login_upload_submit_publish_labels(publisher: NacosPublisher):
    # @lat: [[tests#Registry Contract#Login upload submit publish labels]]
    publisher.login()
    health = publisher.health()
    assert health.get("ok") is True

    skill = publisher.upload_skill("contract-skill", "1.0.0", b"PK skill", overwrite_draft=True)
    assert skill["status"] == "uploaded"
    agent = publisher.upload_agentspec("contract-agent", "1.0.0", b"PK agent", overwrite_draft=True)
    assert agent["status"] == "uploaded"

    publisher.submit("skill", "contract-skill", "1.0.0")
    publisher.submit("agentspec", "contract-agent", "1.0.0")
    publisher.wait_reviewed("agentspec", "contract-agent", "1.0.0", timeout_seconds=5, poll_interval=0.1)

    publisher.publish("skill", "contract-skill", "1.0.0")
    publisher.publish("agentspec", "contract-agent", "1.0.0")
    publisher.set_labels("agentspec", "contract-agent", "1.0.0", {"latest": "true"})
    publisher.set_visibility("agentspec", "contract-agent", "1.0.0", "PRIVATE")

    got = publisher.get_resource("agentspec", "contract-agent", "1.0.0")
    assert got and got["status"] == "online"

    # idempotent same digest path — second upload without overwrite returns draft_exists or uploaded
    again = publisher.upload_agentspec("contract-agent", "1.0.0", b"PK agent", overwrite_draft=False)
    assert again["status"] in {"draft_exists", "conflict", "uploaded"}

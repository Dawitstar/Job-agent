from types import SimpleNamespace

import pytest

from job_agent.digest import format_digest
from job_agent.models import JobPosting
from job_agent.scorer import Score, Scorer, ScoringError, describe_job

JOB = JobPosting(job_id="1", title="Plant Manager", company="IKO North America",
                 location="Brampton, ON", link="https://www.linkedin.com/jobs/view/1/",
                 extra=["Actively recruiting"])


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def fake_client(text='{"score": 72, "reasons": ["Led brewery ops.", " "]}', stop_reason="end_turn"):
    content = [SimpleNamespace(type="text", text=text)] if text is not None else []
    messages = FakeMessages(SimpleNamespace(stop_reason=stop_reason, content=content))
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_score_request_and_parsing():
    client, messages = fake_client()
    result = Scorer("PROFILE", "CV", "claude-sonnet-5-5", client=client).score(JOB)

    assert result == Score(score=72, reasons=["Led brewery ops."])
    call = messages.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    # Profile and CV sit in the cached system prefix; the job is the only user content.
    assert "PROFILE" in call["system"][1]["text"] and "CV" in call["system"][1]["text"]
    assert call["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert call["messages"] == [{"role": "user", "content": describe_job(JOB)}]
    assert "Badges: Actively recruiting" in describe_job(JOB)


def test_score_is_clamped():
    client, _ = fake_client('{"score": 140, "reasons": ["x"]}')
    assert Scorer("p", "c", "m", client=client).score(JOB).score == 100


@pytest.mark.parametrize("stop_reason,text", [("refusal", None), ("max_tokens", '{"sco'), ("end_turn", None)])
def test_unusable_responses_raise(stop_reason, text):
    client, _ = fake_client(text, stop_reason)
    with pytest.raises(ScoringError):
        Scorer("p", "c", "m", client=client).score(JOB)


def test_digest_is_ranked():
    low = JobPosting(job_id="2", title="Commissary Manager", company="Freshslice Pizza",
                     location="Oakville, ON", link="https://www.linkedin.com/jobs/view/2/")
    out = format_digest([(low, Score(20, ["Too junior."])), (JOB, Score(80, ["Good fit."]))])
    assert out.index("Plant Manager") < out.index("Commissary Manager")
    assert " 1. [ 80] Plant Manager @ IKO North America — Brampton, ON" in out

from app.ai import nodes
from app.ai.schemas import DraftReply, TicketClassification


class FakeLLM:
    """Stands in for Gemini: returns the given answers in order and remembers the prompts."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0)


def use_fake_llm(monkeypatch, *answers):
    fake = FakeLLM(*answers)
    # Patch the name nodes.py imported, not app.ai.llm.get_llm: nodes holds its own reference.
    monkeypatch.setattr(nodes, "get_llm", lambda: fake)
    return fake


TICKET = {"ticket_id": 1, "subject": "Where is my order?", "body": "Order 123 is late."}


def test_classify(monkeypatch):
    fake = use_fake_llm(
        monkeypatch,
        TicketClassification(category="shipping", priority="low", sentiment="neutral", confidence=0.9),
    )

    result = nodes.classify(TICKET)

    assert result["category"] == "shipping"
    assert result["classification_confidence"] == 0.9
    # Guards against the bug where the prompt was built without the ticket in it.
    assert "Where is my order?" in fake.prompts[0]


def test_draft_counts_attempts(monkeypatch):
    use_fake_llm(monkeypatch, DraftReply(reply="It ships soon.", confidence=0.8, cited_article_ids=[1]))

    result = nodes.draft({**TICKET, "kb_articles": [], "attempts": 1})

    assert result["draft_reply"] == "It ships soon."
    assert result["attempts"] == 2


def test_quality_check_passes_good_reply():
    state = {"draft_reply": "Hi!", "kb_articles": [{"id": 1}], "cited_article_ids": [1]}
    assert nodes.quality_check(state)["quality_issues"] == []


def test_quality_check_flags_empty_reply():
    state = {"draft_reply": "  ", "kb_articles": [], "cited_article_ids": []}
    assert nodes.quality_check(state)["quality_issues"] == ["empty reply"]


def test_quality_check_flags_made_up_citation():
    state = {"draft_reply": "Hi!", "kb_articles": [{"id": 1}], "cited_article_ids": [7]}
    assert nodes.quality_check(state)["quality_issues"] == ["cites an article that was not retrieved"]

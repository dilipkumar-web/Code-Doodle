import pytest

from app import llm


def test_extract_json_plain():
    assert llm.extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fence_and_chatter():
    text = 'Sure! Here you go:\n```json\n{"a": {"b": 2}}\n```\nHope that helps.'
    assert llm.extract_json(text) == {"a": {"b": 2}}


def test_extract_json_rejects_garbage():
    with pytest.raises(ValueError):
        llm.extract_json("no json here")


def test_normalize_fills_missing_fields_and_strips_fences():
    out = llm.normalize({"code": "```python\nprint(1)\n```", "trace": [{"element": "x"}, "junk"]}, "python")
    assert out["code"] == "print(1)"
    assert out["title"] == "Untitled sketch"
    assert out["trace"] == [{"step": 1, "element": "x", "explanation": "", "state": ""}]
    assert out["uncertainties"] == []


def test_demo_mode_returns_requested_language(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    out = llm.analyze_sketch(b"", "image/jpeg", "cpp")
    assert out["language"] == "cpp" and "int main" in out["code"]
    assert out["diagram_type"] == "flowchart" and len(out["trace"]) >= 3


def test_missing_key_gives_helpful_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("DEMO_MODE", raising=False)
    with pytest.raises(llm.LLMError) as err:
        llm.analyze_sketch(b"", "image/jpeg", "python")
    assert "GEMINI_API_KEY" in str(err.value)

"""A scripted fake chat model, so the LLM code paths can be tested with no API key and no network.

It does NOT prove that a real model classifies well (that needs tests/test_reason_samples_live.py with a key).
It proves the wiring: what goes into each prompt, how replies are parsed, and what the app does on failure.
"""
import json
from typing import Any, Callable, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

RED_WORDS = {
    "sudden_vision_loss": ["can't see", "went dark", "went black", "sudden loss"],
    "curtain_or_shadow": ["curtain", "shadow"],
    "floaters_or_flashes": ["flashes", "floaters since yesterday"],
    "chemical_or_injury": ["floor cleaner", "bleach", "injury", "poked"],
    "severe_pain_headache_haloes": ["severe eye pain", "haloes"],
}


def keyword_red_flag_reply(reason: str) -> str:
    low = reason.lower()
    if "no sudden loss" in low or "gradual" in low:  # the two negation / slow-onset cases of the handout
        return json.dumps({"red_flag": False, "category": "none", "why": "Not a sudden symptom"})
    for cat, words in RED_WORDS.items():
        if any(w in low for w in words):
            return json.dumps({"red_flag": True, "category": cat, "why": f"Mentions {words[0]}"})
    return json.dumps({"red_flag": False, "category": "none", "why": "Routine request"})


class ScriptedChatModel(BaseChatModel):
    """responder(system_text, human_text) -> reply text. Records every prompt in `calls`."""
    responder: Any = None
    calls: Any = None  # Any (not List) so pydantic keeps the SAME list object the test reads

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> ChatResult:
        system = next((m.content for m in messages if m.type == "system"), "")
        human = next((m.content for m in reversed(messages) if m.type == "human"), "")
        self.calls.append({"system": system, "human": human})
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.responder(system, human)))])

    def _stream(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager=None, **kwargs):
        """Streams the same reply in small pieces, like a real model does."""
        system = next((m.content for m in messages if m.type == "system"), "")
        human = next((m.content for m in reversed(messages) if m.type == "human"), "")
        self.calls.append({"system": system, "human": human})
        text = self.responder(system, human)
        for i in range(0, len(text), 25):
            yield ChatGenerationChunk(message=AIMessageChunk(content=text[i:i + 25]))


def fake_summary_reply(human: str) -> str:
    """A well-behaved structured summary built only from what is in the prompt (so it never invents anything)."""
    lines = human.splitlines()
    reason = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Today's reason")), "")
    age = lines[0].split(":", 1)[1].strip() if lines else ""
    visits = []
    for l in lines:
        if l.startswith("- ") and l[2:6].isdigit() and "," in l:
            date, doctor, rest = [x.strip() for x in l[2:].split(",", 2)]
            speciality, note = [x.strip() for x in rest.split(":", 1)]
            visits.append({"date": date, "doctor": doctor, "speciality": speciality, "note": note})
    return json.dumps({"today": reason, "background": f"{age}." + ("" if visits else " No previous visits on record."), "past_visits": visits})


def default_responder(system: str, human: str) -> str:
    """Behaves like a sensible model for each of the three chains, chosen by the system prompt."""
    if "safety check" in system:
        reason = human.split("<reason>")[1].split("</reason>")[0].strip()
        return keyword_red_flag_reply(reason)
    if "summarising what is ALREADY RECORDED" in system:
        return fake_summary_reply(human)
    # fact of the day: a different fact each call
    default_responder.n = getattr(default_responder, "n", 0) + 1
    return f"Fact number {default_responder.n}. Your eyes are remarkable. Extra sentence that must be trimmed."


def make_factory(responder: Callable[[str, str], str] = default_responder, calls: Optional[list] = None):
    shared = calls if calls is not None else []
    return lambda temperature: ScriptedChatModel(responder=responder, calls=shared)

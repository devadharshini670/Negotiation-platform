"""Safety guard for the assistant: the fixed refusal shown when someone asks it to DO something to a
negotiation, and the request detector. (Answers to questions always come from the selected LLM.)"""
import re

REFUSAL = ("I'm an explanation-only assistant, so I can't make, change, accept or reject offers, change personalities, "
           "scenarios, rounds or results, or start, stop or run a negotiation. You stay in control of all of that using "
           "the negotiation screen. I can explain what is happening, why an agent acted the way it did, or what a result means.")

# Messages that ask the assistant to DO something to the negotiation / the app.
_ACTION = re.compile(
    r"^\s*(?:(?:please|pls|kindly)\s+)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?"
    r"(?:make|create|send|submit|place|propose|change|set|switch|update|edit|modify|override|accept|reject|decline|counter|"
    r"start|stop|restart|run|trigger|begin|end|cancel|delete|reset|skip|advance|force|fix|rig|give me the win|"
    r"log\s*out|sign\s*out|disable|enable)\b", re.I)


# Attempts to talk the assistant out of its rules, or to have it act "for me", are refused the same way.
_OVERRIDE = re.compile(
    r"(?:ignore|forget|disregard|bypass|override)\s+(?:all\s+|any\s+|your\s+|the\s+|previous\s+|prior\s+)*(?:rules|instructions|restrictions|guidelines|prompt)"
    r"|\byou\s+are\s+now\b|\bjailbreak\b|\bdeveloper\s+mode\b", re.I)


def is_action_request(text):
    t = (text or '').strip()
    if _OVERRIDE.search(t):
        return True
    if not _ACTION.match(t):
        return False
    # "Accept" / "counter" / "reject" etc. at the start of a *question* about meaning are not requests.
    return not re.match(r"^\s*(?:what|why|how|when|which|who|does|do|is|are)\b", t, re.I)

"""Negotiation Assistant: explains the platform and the user's current negotiation.

ARCHITECTURE BOUNDARY — this package is an explanation layer, not part of the
negotiation. It deliberately imports nothing from the negotiation engine, the
orchestrator, the models or the auth/database code. Its only inputs are plain
dictionaries that the application hands it (a read-only context snapshot), and
its only outside access is a plain-text completion from the LLM provider the
project already uses. The language model gets no tools or functions, so there is
nothing it could call to change an offer, a round, a personality or a result.
tests/test_assistant.py enforces the import rule."""

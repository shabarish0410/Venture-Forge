"""Vendor transport and response normalization, isolated from domain operations."""
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class ProviderResult:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    status: str


def openai(profile, settings, instructions, payload, schema, output_cap, client):
    response = client.post("https://api.openai.com/v1/responses", headers={"Authorization": "Bearer " + settings.openai_api_key.get_secret_value()}, json={"model": profile.model_id, "instructions": instructions, "input": payload, "store": False, "max_output_tokens": output_cap, "text": {"format": {"type": "json_schema", "name": "specialist_analysis", "strict": True, "schema": schema}}})
    response.raise_for_status()
    body = response.json()
    parts = [c for block in body.get("output", []) if block.get("type") == "message" for c in block.get("content", [])]
    text = "".join(c.get("text", "") for c in parts if c.get("type") == "output_text")
    status = "REFUSED" if any(c.get("type") == "refusal" for c in parts) else "COMPLETE" if body.get("status") == "completed" else "INCOMPLETE"
    usage = body.get("usage", {})
    return ProviderResult(text, usage.get("input_tokens"), usage.get("output_tokens"), status)


def anthropic(profile, settings, instructions, payload, schema, output_cap, client):
    response = client.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": settings.anthropic_api_key.get_secret_value(), "anthropic-version": "2023-06-01"}, json={"model": profile.model_id, "max_tokens": output_cap, "system": instructions, "messages": [{"role": "user", "content": payload}], "output_config": {"format": {"type": "json_schema", "schema": schema}}})
    response.raise_for_status()
    body = response.json()
    text = "".join(block.get("text", "") for block in body.get("content", []) if block.get("type") == "text")
    status = "REFUSED" if body.get("stop_reason") == "refusal" else "COMPLETE" if body.get("stop_reason") == "end_turn" else "INCOMPLETE"
    usage = body.get("usage", {})
    tokens = usage.get("input_tokens")
    if isinstance(tokens, int): tokens += usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
    return ProviderResult(text, tokens, usage.get("output_tokens"), status)


def gemini(profile, settings, instructions, payload, schema, output_cap, client):
    model = profile.model_id.removeprefix("models/")
    response = client.post("https://generativelanguage.googleapis.com/v1beta/models/" + quote(model, safe="") + ":generateContent", headers={"x-goog-api-key": settings.gemini_api_key.get_secret_value()}, json={"systemInstruction": {"parts": [{"text": instructions}]}, "contents": [{"role": "user", "parts": [{"text": payload}]}], "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema, "maxOutputTokens": output_cap}})
    response.raise_for_status()
    body = response.json()
    candidates = body.get("candidates", [])
    candidate = candidates[0] if candidates else {}
    text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if not p.get("thought"))
    blocked = body.get("promptFeedback", {}).get("blockReason") or candidate.get("finishReason") in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"}
    status = "REFUSED" if blocked else "COMPLETE" if candidate.get("finishReason") == "STOP" else "INCOMPLETE"
    usage = body.get("usageMetadata", {})
    output = usage.get("candidatesTokenCount")
    if isinstance(output, int): output += usage.get("thoughtsTokenCount", 0)
    return ProviderResult(text, usage.get("promptTokenCount"), output, status)


def ollama(profile, settings, instructions, payload, schema, output_cap, client):
    response = client.post(settings.ollama_url.rstrip("/") + "/api/chat", json={"model": profile.model_id, "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": payload}], "format": schema, "stream": False, "options": {"num_predict": output_cap, "temperature": 0}})
    response.raise_for_status()
    body = response.json()
    status = "COMPLETE" if body.get("done", True) and body.get("done_reason", "stop") == "stop" else "INCOMPLETE"
    return ProviderResult(body.get("message", {}).get("content", ""), body.get("prompt_eval_count"), body.get("eval_count"), status)


ADAPTERS = {"openai": openai, "anthropic": anthropic, "gemini": gemini, "ollama": ollama}

"""Capability/budget routing; privacy policy is never relaxed as a fallback."""
from dataclasses import dataclass
from urllib.parse import urlparse
from venture_forge.shared.model_config import ModelProfile, ModelRequirements

LEVEL = {"basic": 0, "standard": 1, "high": 2}


class RoutingError(Exception):
    pass


def profiles(settings):
    if settings.model_router_policy == "disabled": return []
    if settings.model_profiles: return settings.model_profiles
    if settings.model_provider == "disabled" or not settings.model_id: return []
    # The original single-provider config is only a compatibility profile, never an agent binding.
    return [ModelProfile(name="legacy-default", provider=settings.model_provider, model_id=settings.model_id, reasoning="standard", context_tokens=32768, max_output_tokens=2048, input_inr_per_million=settings.model_input_inr_per_million, output_inr_per_million=settings.model_output_inr_per_million)]


def ready(profile, settings):
    if not profile.enabled: return False
    if profile.provider == "ollama":
        url = urlparse(settings.ollama_url)
        return url.scheme in {"http", "https"} and url.hostname in {"localhost", "127.0.0.1", "::1"} and not url.username and not url.password and not url.query and not url.fragment
    key = getattr(settings, {"openai": "openai_api_key", "anthropic": "anthropic_api_key", "gemini": "gemini_api_key"}[profile.provider])
    return bool(key.get_secret_value()) and profile.input_inr_per_million > 0 and profile.output_inr_per_million > 0


def catalog(settings):
    return [{**p.model_dump(mode="json"), "ready": ready(p, settings), "location": "local" if p.provider == "ollama" else "cloud"} for p in profiles(settings)]


@dataclass(frozen=True)
class Route:
    profile: ModelProfile | None
    reason: str
    requirements: ModelRequirements
    input_token_bound: int
    output_token_cap: int
    reserved_cost_inr: float = 0
    policy: str = "hybrid-v1"

    def snapshot(self):
        return {"policy": self.policy, "engine": "MODEL" if self.profile else "RULE", "profile": self.profile.name if self.profile else None, "provider": self.profile.provider if self.profile else None, "model": self.profile.model_id if self.profile else None, "reason": self.reason, "requirements": self.requirements.model_dump(mode="json"), "input_token_bound": self.input_token_bound, "output_token_cap": self.output_token_cap, "reserved_cost_inr": self.reserved_cost_inr, "price_snapshot": {"input_inr_per_million": self.profile.input_inr_per_million, "output_inr_per_million": self.profile.output_inr_per_million} if self.profile else None}


def select_route(settings, requirements, input_bound, budget, *, mode="AUTO", data_policy="cloud_allowed", allow_processing=False, preferred_profile=None):
    if mode == "RULE": return Route(None, "DETERMINISTIC_REQUESTED", requirements, input_bound, 0)
    configured = [p for p in profiles(settings) if ready(p, settings)]
    if not configured:
        if mode == "AUTO" and not preferred_profile: return Route(None, "NO_MODEL_CONFIGURED", requirements, input_bound, 0)
        raise RoutingError("MODEL_NOT_CONFIGURED")
    permitted = [p for p in configured if data_policy != "local_only" or p.provider == "ollama"]
    if preferred_profile: permitted = [p for p in permitted if p.name == preferred_profile]
    if not permitted: raise RoutingError("NO_PRIVACY_COMPATIBLE_MODEL" if data_policy == "local_only" else "PROFILE_UNAVAILABLE")
    if not allow_processing: raise RoutingError("MODEL_PERMISSION_REQUIRED")
    capable = [p for p in permitted if LEVEL[p.reasoning] >= LEVEL[requirements.reasoning] and p.context_tokens >= max(requirements.min_context_tokens, input_bound + requirements.max_output_tokens) and p.max_output_tokens >= requirements.max_output_tokens and (not requirements.structured_outputs or p.structured_outputs) and (not requirements.tool_calling or p.tool_calling)]
    if not capable: raise RoutingError("NO_CAPABLE_MODEL")
    affordable = []
    for p in capable:
        reserve = (input_bound * p.input_inr_per_million + requirements.max_output_tokens * p.output_inr_per_million) / 1000000
        if reserve <= budget["max_cost_inr"]: affordable.append((p, reserve))
    if not affordable: raise RoutingError("MODEL_COST_CAP")
    # Cloud is the default for complex tasks. Explicit local-only scope is a hard constraint.
    def rank(item):
        p, cost = item
        return (p.provider == "ollama" if requirements.reasoning == "high" and data_policy == "cloud_allowed" else False, cost, LEVEL[p.reasoning] - LEVEL[requirements.reasoning], p.priority, p.name)
    profile, reserve = min(affordable, key=rank)
    reason = "LOCAL_PRIVACY_POLICY" if data_policy == "local_only" else "PROFILE_REQUESTED" if preferred_profile else "CLOUD_COMPLEX_TASK" if requirements.reasoning == "high" and profile.provider != "ollama" else "CAPABILITY_AND_COST"
    return Route(profile, reason, requirements, input_bound, requirements.max_output_tokens, reserve)

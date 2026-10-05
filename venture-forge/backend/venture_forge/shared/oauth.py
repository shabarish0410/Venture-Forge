"""Fixed provider transports; no provider token is sent to or stored by the UI."""
from dataclasses import dataclass
import base64
import hashlib
import re
import secrets
from urllib.parse import urlencode, urlsplit
import httpx
import jwt

PROVIDERS = {"google": "Google", "github": "GitHub"}
AUTHORIZE = {"google": "https://accounts.google.com/o/oauth2/v2/auth", "github": "https://github.com/login/oauth/authorize"}
TOKEN = {"google": "https://oauth2.googleapis.com/token", "github": "https://github.com/login/oauth/access_token"}
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"


class OAuthFailure(Exception):
    def __init__(self, code="invalid_provider_response"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, repr=False)
class ProviderIdentity:
    subject: str
    email: str
    name: str
    avatar_url: str | None = None
    email_verified: bool = True


def configured(settings, provider):
    return bool(getattr(settings, f"{provider}_client_id", "").strip() and getattr(settings, f"{provider}_client_secret").get_secret_value().strip())


def callback_uri(settings, provider):
    return f"{settings.app_origin}/api/v1/auth/oauth/{provider}/callback"


def code_challenge(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def authorization_url(settings, provider, state, verifier, nonce):
    values = {
        "client_id": getattr(settings, f"{provider}_client_id"),
        "redirect_uri": callback_uri(settings, provider),
        "response_type": "code", "state": state,
        "code_challenge": code_challenge(verifier), "code_challenge_method": "S256",
        "scope": "openid email profile" if provider == "google" else "user:email",
    }
    if provider == "google":
        values.update(nonce=nonce, prompt="select_account", access_type="online")
    else:
        values["prompt"] = "select_account"
    return AUTHORIZE[provider] + "?" + urlencode(values)


def verified_email(value):
    if value is None or value == "":
        raise OAuthFailure("email_unavailable")
    if not isinstance(value, str) or not 3 <= len(value) <= 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise OAuthFailure("unverified_email")
    return value.strip().lower()


def avatar_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def _json(response):
    response.raise_for_status()
    if len(response.content) > 1000000:
        raise OAuthFailure()
    return response.json()


def _google_identity(client, tokens, settings, nonce):
    encoded = tokens.get("id_token")
    if not isinstance(encoded, str) or not 1 <= len(encoded) <= 65536:
        raise OAuthFailure()
    header = jwt.get_unverified_header(encoded)
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise OAuthFailure()
    keyset = _json(client.get(GOOGLE_JWKS))
    if not isinstance(keyset, dict) or not isinstance(keyset.get("keys"), list):
        raise OAuthFailure()
    matches = [key for key in keyset["keys"] if isinstance(key, dict) and key.get("kid") == header["kid"] and key.get("kty") == "RSA" and key.get("use", "sig") == "sig"]
    if len(matches) != 1:
        raise OAuthFailure()
    key = jwt.PyJWK.from_dict(matches[0], algorithm="RS256").key
    claims = jwt.decode(encoded, key, algorithms=["RS256"], audience=settings.google_client_id,
        issuer=["https://accounts.google.com", "accounts.google.com"], leeway=30,
        options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]})
    returned_nonce = claims.get("nonce")
    if not isinstance(returned_nonce, str) or not secrets.compare_digest(returned_nonce.encode(), nonce.encode()):
        raise OAuthFailure()
    if claims.get("azp", settings.google_client_id) != settings.google_client_id:
        raise OAuthFailure()
    if isinstance(claims["aud"], list) and len(claims["aud"]) > 1 and claims.get("azp") != settings.google_client_id:
        raise OAuthFailure()
    email = verified_email(claims.get("email"))
    if claims.get("email_verified") is not True:
        raise OAuthFailure("unverified_email")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
        raise OAuthFailure()
    name = claims.get("name")
    return ProviderIdentity(subject, email, (name.strip()[:100] if isinstance(name, str) else "") or "Founder", avatar_url(claims.get("picture")))


def _github_identity(client, tokens):
    token = tokens.get("access_token")
    token_type = tokens.get("token_type")
    if not isinstance(token, str) or not 1 <= len(token) <= 8192 or not re.fullmatch(r"[\x21-\x7e]+", token) or not isinstance(token_type, str) or token_type.lower() != "bearer":
        raise OAuthFailure()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    user = _json(client.get("https://api.github.com/user", headers=headers))
    emails = _json(client.get("https://api.github.com/user/emails", params={"per_page": 100}, headers=headers))
    if not isinstance(user, dict) or type(user.get("id")) is not int or user["id"] <= 0 or not isinstance(emails, list):
        raise OAuthFailure()
    if not emails:
        raise OAuthFailure("email_unavailable")
    verified = [item for item in emails if isinstance(item, dict) and item.get("verified") is True]
    if not verified:
        raise OAuthFailure("unverified_email")
    chosen = next((item for item in verified if item.get("primary") is True), verified[0])
    name = user.get("name") or user.get("login")
    return ProviderIdentity(str(user["id"]), verified_email(chosen.get("email")), (name.strip()[:100] if isinstance(name, str) else "") or "Founder", avatar_url(user.get("avatar_url")))


def exchange_identity(settings, provider, code, verifier, nonce):
    """Exchange a one-use code, verify identity, then discard provider tokens."""
    try:
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            tokens = _json(client.post(TOKEN[provider], data={
                "client_id": getattr(settings, f"{provider}_client_id"),
                "client_secret": getattr(settings, f"{provider}_client_secret").get_secret_value(),
                "code": code, "code_verifier": verifier, "redirect_uri": callback_uri(settings, provider),
                "grant_type": "authorization_code",
            }, headers={"Accept": "application/json"}))
            if isinstance(tokens, dict) and tokens.get("error") in {"redirect_uri_mismatch", "bad_redirect_uri"}:
                raise OAuthFailure("callback_mismatch")
            if not isinstance(tokens, dict) or tokens.get("error"):
                raise OAuthFailure()
            return _google_identity(client, tokens, settings, nonce) if provider == "google" else _github_identity(client, tokens)
    except OAuthFailure:
        raise
    except httpx.HTTPError:
        raise OAuthFailure("provider_unavailable") from None
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError):
        raise OAuthFailure() from None

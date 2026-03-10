"""
Auth helpers for 9host API.

Uses Cognito GetUser to validate access tokens (no JWT lib required).
"""


def _get_auth_header(event: dict) -> str:
    """Extract Authorization header value."""
    headers = event.get("headers") or {}
    if isinstance(headers, dict):
        return headers.get("authorization") or headers.get("Authorization") or ""
    for h in headers:
        k = (h.get("key") or h.get("Key") or "").lower()
        if k == "authorization":
            return h.get("value") or h.get("Value") or ""
    return ""


def get_sub_from_access_token(event: dict, region: str = "us-east-1") -> str | None:
    """
    Extract Cognito sub from Bearer token via GetUser.
    Returns sub or None if missing/invalid.
    """
    import boto3

    auth = _get_auth_header(event)
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None

    try:
        client = boto3.client("cognito-idp", region_name=region)
        resp = client.get_user(AccessToken=token)
        for attr in resp.get("UserAttributes", []):
            if attr.get("Name") == "sub":
                return attr.get("Value")
        return resp.get("Username")  # fallback
    except Exception:
        return None

"""Read and validate caller-owned Plane connection settings."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from ipaddress import ip_address
import re
import socket
from urllib.parse import SplitResult, urlsplit, urlunsplit


AUTHORIZATION_HEADER = "Authorization"
API_KEY_HEADER = "X-Plane-Api-Key"
WORKSPACE_HEADER = "X-Plane-Workspace-Slug"
API_HOST_HEADER = "X-Plane-Api-Host-Url"

Resolver = Callable[..., list[tuple]]

_WORKSPACE_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")


class InvalidPlaneRequestConfig(ValueError):
    """The MCP request did not contain a safe, complete Plane configuration."""


@dataclass(frozen=True, slots=True)
class PlaneRequestConfig:
    """The three Plane values supplied by one MCP caller."""

    api_key: str = field(repr=False)
    workspace_slug: str
    api_host_url: str

    @classmethod
    def from_headers(
        cls,
        headers: Mapping[str, str],
        *,
        resolver: Resolver = socket.getaddrinfo,
    ) -> PlaneRequestConfig:
        normalized_headers = {name.lower(): value for name, value in headers.items()}
        caller_api_key = normalized_headers.get(API_KEY_HEADER.lower(), "").strip()
        authorization = normalized_headers.get(AUTHORIZATION_HEADER.lower(), "").strip()
        bearer_api_key = ""
        if authorization:
            scheme, separator, bearer_api_key = authorization.partition(" ")
            if (
                not separator
                or scheme.lower() != "bearer"
                or not bearer_api_key.strip()
            ):
                raise InvalidPlaneRequestConfig(
                    f"{AUTHORIZATION_HEADER} must contain a non-empty Bearer API key"
                )
            bearer_api_key = bearer_api_key.strip()
        if caller_api_key and bearer_api_key and caller_api_key != bearer_api_key:
            raise InvalidPlaneRequestConfig(
                f"{API_KEY_HEADER} and {AUTHORIZATION_HEADER} must contain the same API key"
            )
        api_key = caller_api_key or bearer_api_key
        if not api_key:
            raise InvalidPlaneRequestConfig(f"{API_KEY_HEADER} is required")

        workspace_slug = normalized_headers.get(WORKSPACE_HEADER.lower(), "").strip()
        if not workspace_slug:
            raise InvalidPlaneRequestConfig(f"{WORKSPACE_HEADER} is required")
        if not _WORKSPACE_SLUG_PATTERN.fullmatch(workspace_slug):
            raise InvalidPlaneRequestConfig(
                f"{WORKSPACE_HEADER} is not a valid workspace slug"
            )

        api_host_url = normalized_headers.get(API_HOST_HEADER.lower(), "").strip()
        if not api_host_url:
            raise InvalidPlaneRequestConfig(f"{API_HOST_HEADER} is required")

        return cls(
            api_key=api_key,
            workspace_slug=workspace_slug,
            api_host_url=validate_plane_api_host_url(api_host_url, resolver=resolver),
        )


def validate_plane_api_host_url(
    value: str,
    *,
    resolver: Resolver = socket.getaddrinfo,
) -> str:
    """Return a normalized public HTTPS Plane root URL or raise."""

    try:
        parsed = urlsplit(value.strip())
        port = parsed.port or 443
    except ValueError as exc:
        raise InvalidPlaneRequestConfig(
            f"{API_HOST_HEADER} is not a valid URL"
        ) from exc

    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise InvalidPlaneRequestConfig(f"{API_HOST_HEADER} must be an HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidPlaneRequestConfig(
            f"{API_HOST_HEADER} must not contain user information"
        )
    if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise InvalidPlaneRequestConfig(
            f"{API_HOST_HEADER} must be a root URL without path, query, or fragment"
        )

    hostname = parsed.hostname.rstrip(".").lower()
    if (
        hostname == "localhost"
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
    ):
        raise InvalidPlaneRequestConfig(
            f"{API_HOST_HEADER} must resolve to a public IP address"
        )

    try:
        addresses = resolver(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise InvalidPlaneRequestConfig(
            f"{API_HOST_HEADER} hostname could not be resolved"
        ) from exc
    if not addresses:
        raise InvalidPlaneRequestConfig(
            f"{API_HOST_HEADER} hostname could not be resolved"
        )

    try:
        resolved_ips = {ip_address(address[4][0]) for address in addresses}
    except (IndexError, TypeError, ValueError) as exc:
        raise InvalidPlaneRequestConfig(
            f"{API_HOST_HEADER} returned an invalid DNS result"
        ) from exc
    if not resolved_ips or any(
        not resolved_ip.is_global for resolved_ip in resolved_ips
    ):
        raise InvalidPlaneRequestConfig(
            f"{API_HOST_HEADER} must resolve only to public IP addresses"
        )

    host_for_url = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host_for_url if port == 443 else f"{host_for_url}:{port}"
    normalized = SplitResult("https", netloc, "", "", "")
    return urlunsplit(normalized)

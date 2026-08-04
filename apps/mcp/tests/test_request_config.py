from __future__ import annotations

import socket

import pytest

from plane_mcp_gateway.request_config import (
    InvalidPlaneRequestConfig,
    PlaneRequestConfig,
    validate_plane_api_host_url,
)


def public_resolver(host: str, port: int, *, type: int):
    assert host == "plane.example.com"
    assert port == 443
    assert type == socket.SOCK_STREAM
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def private_resolver(host: str, port: int, *, type: int):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", port))]


def test_request_config_requires_all_three_caller_values():
    with pytest.raises(InvalidPlaneRequestConfig, match="X-Plane-Workspace-Slug"):
        PlaneRequestConfig.from_headers(
            {
                "authorization": "Bearer plane_api_key",
                "x-plane-api-host-url": "https://plane.example.com",
            }
        )


def test_request_config_reads_api_key_workspace_and_host_from_headers():
    config = PlaneRequestConfig.from_headers(
        {
            "x-plane-api-key": "plane_api_key",
            "x-plane-workspace-slug": "aidong",
            "x-plane-api-host-url": "https://plane.example.com/",
        },
        resolver=public_resolver,
    )

    assert config.api_key == "plane_api_key"
    assert config.workspace_slug == "aidong"
    assert config.api_host_url == "https://plane.example.com"


def test_request_config_reads_query_values_and_uses_request_origin_as_host():
    config = PlaneRequestConfig.from_headers(
        {},
        query_params={
            "PLANE_API_KEY": "query_api_key",
            "PLANE_WORKSPACE_SLUG": "aidong",
        },
        default_api_host_url="https://plane.example.com",
        resolver=public_resolver,
    )

    assert config.api_key == "query_api_key"
    assert config.workspace_slug == "aidong"
    assert config.api_host_url == "https://plane.example.com"


def test_request_config_rejects_conflicting_header_and_query_values():
    with pytest.raises(InvalidPlaneRequestConfig, match="Conflicting"):
        PlaneRequestConfig.from_headers(
            {
                "x-plane-api-key": "header_api_key",
                "x-plane-workspace-slug": "aidong",
                "x-plane-api-host-url": "https://plane.example.com",
            },
            query_params={"plane_api_key": "query_api_key"},
            resolver=public_resolver,
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://plane.example.com",
        "https://user:pass@plane.example.com",
        "https://plane.example.com/api/v1",
        "https://plane.example.com?redirect=https://internal.example",
        "https://localhost",
    ],
)
def test_plane_host_rejects_unsafe_url_shapes(url: str):
    with pytest.raises(InvalidPlaneRequestConfig):
        validate_plane_api_host_url(url, resolver=public_resolver)


def test_plane_host_rejects_private_dns_results():
    with pytest.raises(InvalidPlaneRequestConfig, match="public IP"):
        validate_plane_api_host_url(
            "https://plane.example.com", resolver=private_resolver
        )

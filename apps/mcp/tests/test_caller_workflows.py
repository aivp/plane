"""从调用方使用的 MCP HTTP 入口验证旧工具约定。"""

import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from starlette.testclient import TestClient
from test_app import mcp_headers, public_resolver

from plane_mcp_gateway.app import create_app


@pytest.fixture
def gateway():
    # 使用合成凭据，所有 Plane 请求均由各用例在 HTTP 传输层接管。
    async def accept(config):
        return True

    with TestClient(
        create_app(api_key_validator=accept, resolver=public_resolver)
    ) as client:
        yield client


def rpc(client, method, params, headers=None):
    response = client.post(
        "/mcp",
        headers=headers or mcp_headers(),
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )
    response.raise_for_status()
    return response.json()["result"]


def call(client, name, /, **arguments):
    result = rpc(client, "tools/call", {"name": name, "arguments": arguments})
    assert not result["isError"], result["content"]
    return result


def page(row):
    return {
        "results": [row],
        "count": 1,
        "total_count": 1,
        "total_results": 1,
        "total_pages": 1,
        "next_cursor": "",
        "prev_cursor": "",
        "next_page_results": False,
        "prev_page_results": False,
    }


def response(data):
    reply = requests.Response()
    reply.status_code = 200
    reply.headers["Content-Type"] = "application/json"
    reply._content = json.dumps(data).encode()
    return reply


def test_project_description_customer_label_and_review(gateway, monkeypatch):
    project = {
        "id": "p",
        "identifier": "QA",
        "name": "测试项目",
        "description": "项目描述",
    }
    label = {"id": "customer", "name": "客户 A"}
    item = {"id": "i", "sequence_id": 12}

    # 模拟有状态的 Plane API，以实际 PATCH 请求判断原负责人有无丢失。
    def send(session, request, **kwargs):
        url = urlsplit(request.url)
        path = url.path.removeprefix("/api/v1/workspaces/caller-workspace/")
        assert request.headers["X-Api-Key"] == "caller-api-key"
        if path == "projects-lite/":
            assert "per_page" not in parse_qs(url.query)
            return response(page(project))
        if path == "projects/p/":
            return response(project)
        if path == "projects/p/labels/":
            assert parse_qs(url.query)["per_page"] == ["25"]
            return response(page(label))
        if request.method in ("POST", "PATCH"):
            assert path == (
                "projects/p/work-items/"
                if request.method == "POST"
                else "projects/p/work-items/i/"
            )
            item.update(json.loads(request.body))
        else:
            assert path == "projects/p/work-items/i/"
        return response(item)

    monkeypatch.setattr(requests.Session, "send", send)
    projects = call(gateway, "list_projects")["structuredContent"]
    assert projects["results"][0]["description"] == "项目描述"
    assert (
        call(gateway, "retrieve_project", project_id="p")["structuredContent"][
            "description"
        ]
        == "项目描述"
    )
    labels = call(gateway, "list_labels", project_id="p", params={"per_page": 25})
    assert labels["structuredContent"]["result"][0]["name"] == "客户 A"
    created = call(
        gateway,
        "create_work_item",
        project_id="p",
        name="测试工单",
        labels=[label["id"]],
        assignees=["owner"],
    )["structuredContent"]
    assert (created["id"], created["sequence_id"], created["labels"]) == (
        "i",
        12,
        ["customer"],
    )
    reviewed = call(
        gateway,
        "manage_work_item_assignee",
        project_id="p",
        work_item_id="i",
        add_user_id="reviewer",
    )["structuredContent"]
    assert reviewed["assignees"] == item["assignees"] == ["owner", "reviewer"]


@pytest.mark.parametrize("via_resource", [False, True])
def test_concurrent_caller_config_reaches_sdk(gateway, monkeypatch, via_resource):
    # 使用屏障让两个租户同时抵达出站传输，检查每个请求的三项配置。
    barrier = Barrier(2, timeout=10)

    def send(session, request, **kwargs):
        tenant = urlsplit(request.url).hostname.split(".")[0]
        suffix = "projects/p/" if via_resource else "projects-lite/"
        assert urlsplit(request.url).path == f"/api/v1/workspaces/{tenant}/{suffix}"
        assert request.headers["X-Api-Key"] == f"key-{tenant}"
        barrier.wait()
        row = {"identifier": "QA", "id": tenant, "name": tenant}
        return response(row if via_resource else page(row))

    monkeypatch.setattr(requests.Session, "send", send)

    def list_for(tenant):
        headers = mcp_headers(
            **{
                "X-Plane-Api-Key": f"key-{tenant}",
                "X-Plane-Workspace-Slug": tenant,
                "X-Plane-Api-Host-Url": f"https://{tenant}.example.com",
            }
        )
        params = (
            {"name": "retrieve_project", "arguments": {"project_id": "p"}}
            if via_resource
            else {"name": "list_projects", "arguments": {}}
        )
        result = rpc(gateway, "tools/call", params, headers)
        assert not result["isError"], result["content"]
        data = json.loads(result["content"][0]["text"])
        return data["id"] if via_resource else data["results"][0]["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(list_for, ("alpha", "beta"))) == ["alpha", "beta"]


@pytest.mark.parametrize(
    "name,args",
    [
        ("create_release", {}),
        ("update_workspace_features", {}),
        ("project", {"action": "update_features"}),
        ("workitem", {"action": "delete"}),
    ],
)
def test_unlisted_operations_are_uncallable(gateway, name, args):
    # 直接按名字调用，检查网关拒绝未知工具而非仅隐藏发现结果。
    result = rpc(gateway, "tools/call", {"name": name, "arguments": args})
    assert result["isError"] and "unknown tool" in result["content"][0]["text"].lower()


def test_url_attachment_upload_and_readback(gateway, monkeypatch):
    import socket

    import urllib3

    payload = b"Plane QA attachment"
    source = "https://files.example.com/qa.txt"
    record = {"asset": "qa.txt", "id": "attachment", "is_uploaded": False}

    # 给旧版和新版下载器提供同一份公网文件，保留新版 URL 校验和限长读取逻辑。
    def resolve(host, port, *args, **kwargs):
        assert host == "files.example.com"
        return public_resolver(host, port, type=socket.SOCK_STREAM)

    def download(pool, method, path, **kwargs):
        assert method == "GET" and path == "/qa.txt" and pool.host == "93.184.216.34"
        return urllib3.response.HTTPResponse(
            body=BytesIO(payload),
            headers={"Content-Type": "text/plain"},
            preload_content=False,
        )

    # 模拟 Plane 的签名申请、对象存储接收字节、上传确认及回查。
    def send(session, request, **kwargs):
        url = urlsplit(request.url)
        if request.url == source:
            reply = response(None)
            reply._content = payload
            reply.headers["Content-Type"] = "text/plain"
            return reply
        if url.hostname == "storage.example.com":
            assert payload in request.body and "X-Api-Key" not in request.headers
            return response({})
        assert url.hostname == "plane.example.com"
        assert request.headers["X-Api-Key"] == "caller-api-key"
        assert url.path.startswith(
            "/api/v1/workspaces/caller-workspace/projects/p/work-items/i/attachments/"
        )
        if request.method == "POST":
            record["attributes"] = json.loads(request.body)
            return response(
                {
                    "asset_id": record["id"],
                    "attachment": record,
                    "upload_data": {"url": "https://storage.example.com/upload"},
                }
            )
        if request.method == "PATCH":
            assert url.path.endswith("/attachment/")
            record.update(json.loads(request.body))
            return response({})
        assert request.method == "GET"
        return response([record])

    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(urllib3.HTTPSConnectionPool, "urlopen", download)
    monkeypatch.setattr(requests.Session, "send", send)
    arguments = {"project_id": "p", "work_item_id": "i"}
    uploaded = call(
        gateway, "upload_work_item_attachment_from_url", **arguments, url=source
    )
    attachment = uploaded["structuredContent"]
    assert (
        attachment["id"],
        attachment["name"],
        attachment["size"],
        attachment["content_type"],
    ) == (
        "attachment",
        "qa.txt",
        len(payload),
        "text/plain",
    )
    listed = call(gateway, "list_work_item_attachments", **arguments)
    assert listed["structuredContent"]["result"][0]["is_uploaded"] is True


def test_update_only_sends_supplied_fields(gateway, monkeypatch):
    # SDK 0.3.1 区分未设置与显式 null；旧工具两个情形都应省略字段。
    bodies = []

    def send(session, request, **kwargs):
        bodies.append(json.loads(request.body))
        return response({"id": "i"})

    monkeypatch.setattr(requests.Session, "send", send)
    call(
        gateway,
        "update_work_item",
        project_id="p",
        work_item_id="i",
        state="review",
        labels=None,
        target_date=None,
        is_draft=False,
        point=0,
    )
    assert bodies == [{"state": "review", "is_draft": False, "point": 0}]


def test_empty_project_cannot_select_workspace_states(gateway, monkeypatch):
    # 旧项目工具没有工作区级操作；空项目 ID 也不得切换操作范围。
    paths = []

    def send(session, request, **kwargs):
        paths.append(urlsplit(request.url).path)
        return response({})

    monkeypatch.setattr(requests.Session, "send", send)
    rpc(
        gateway,
        "tools/call",
        {"name": "delete_state", "arguments": {"project_id": "", "state_id": "s"}},
    )
    assert all("/projects/" in path for path in paths)


@pytest.mark.parametrize("extra", [{}, {"parent": None}, {"parent": "top"}])
def test_comment_fields_match_plane_payload(gateway, monkeypatch, extra):
    # 旧模型允许后端扩展字段；既不能补出缺失的 parent，也不能删掉显式返回的值。
    def send(session, request, **kwargs):
        return response({"project": "p", "workspace": "w", **extra})

    monkeypatch.setattr(requests.Session, "send", send)
    comment = call(
        gateway,
        "retrieve_work_item_comment",
        project_id="p",
        work_item_id="i",
        comment_id="c",
    )["structuredContent"]
    assert {k: comment[k] for k in comment if k == "parent"} == extra


@pytest.mark.parametrize("scope", ["project", "module", "cycle"])
@pytest.mark.parametrize("archive", [False, True])
def test_legacy_archive_routes(gateway, monkeypatch, scope, archive):
    # 三个旧工具均没有上游别名；两个方向分别验证，周期保留布尔返回值。
    sent = []

    def send(session, request, **kwargs):
        sent.append((request.method, urlsplit(request.url).path))
        if request.method == "GET":
            return response(
                {
                    "name": "Q",
                    "owned_by": "u",
                    "project": "p",
                    "workspace": "w",
                    "end_date": "2000-01-01",
                }
            )
        return response(True)

    monkeypatch.setattr(requests.Session, "send", send)
    args = {"project_id": "p", "archive": archive}
    if scope != "project":
        args[scope + "_id"] = "x"
    result = call(gateway, "manage_" + scope + "_archive", **args)
    suffix = "/archive/" if archive or scope == "project" else "/unarchive/"
    assert sent[-1][1].endswith(suffix)
    assert sent[-1][0] == ("POST" if archive else "DELETE")
    if scope == "cycle":
        assert result["structuredContent"] == {"result": True}


def test_upload_rejects_unsupported_source_scheme(gateway, monkeypatch):
    # 在网关入口验证新版下载器先检查协议，拒绝时不创建附件记录。
    def unexpected_request(*args, **kwargs):
        pytest.fail("意外的出站请求")

    monkeypatch.setattr(requests.Session, "send", unexpected_request)
    result = rpc(
        gateway,
        "tools/call",
        {
            "name": "upload_work_item_attachment_from_url",
            "arguments": {
                "project_id": "p",
                "work_item_id": "i",
                "url": "ftp://files.example.com/qa.txt",
            },
        },
    )
    assert (
        result["isError"] and "Unsupported URL scheme" in result["content"][0]["text"]
    )


def test_old_name_rejects_caller_selected_action(gateway, monkeypatch):
    # 固定旧名只允许旧签名；通用资源的 action 不是合法参数。
    def unexpected_request(*args, **kwargs):
        pytest.fail("网关在参数校验前调用了 Plane")

    monkeypatch.setattr(requests.Session, "send", unexpected_request)
    result = rpc(
        gateway,
        "tools/call",
        {
            "name": "list_projects",
            "arguments": {"action": "update_features"},
        },
    )
    assert result["isError"]
    assert "action" in result["content"][0]["text"]


def test_delete_with_empty_identifier_fails(gateway):
    # 上游以文本提示缺失参数，旧删除工具返回 None，转换时不能吞掉这个错误。
    result = rpc(
        gateway,
        "tools/call",
        {
            "name": "delete_work_item",
            "arguments": {"project_id": "p", "work_item_id": ""},
        },
    )
    assert result["isError"]


def test_my_todos_link_does_not_read_plane_work_items(gateway, monkeypatch):
    # 生成链接不应使用共享密钥读取任务或机器人身份。
    def unexpected_api_call(*args, **kwargs):
        pytest.fail("生成待办链接时访问了 Plane 业务 API")

    monkeypatch.setattr(requests.Session, "send", unexpected_api_call)
    result = call(gateway, "get_my_todos_link")
    assert result["content"][0]["text"] == (
        "[打开我的待办](https://plane.example.com/caller-workspace/workspace-views/my-todos/)"
    )

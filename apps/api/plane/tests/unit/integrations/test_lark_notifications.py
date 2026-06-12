# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace
from uuid import uuid4

import pytest

from plane.bgtasks.lark_task import _outbox_card
from plane.db.models import Account, LarkNotificationOutbox, Notification
from plane.integrations.lark import notifications as lark_notifications
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory


def _details(card):
    return {detail["label"]: detail["value"] for detail in card["details"]}


def _make_notification(
    *,
    field="state",
    verb="updated",
    old_value="",
    new_value="",
    issue_comment="",
    sender="in_app:issue_activities:subscriber",
    message_stripped="",
):
    actor = UserFactory(email="actor@example.com", username="actor", display_name="张三")
    receiver = UserFactory(email="receiver@example.com", username="receiver", display_name="李四")
    workspace = WorkspaceFactory(owner=actor, name="研发空间", slug="rd")
    project = ProjectFactory(workspace=workspace, name="支付系统", identifier="PAY")
    issue_id = uuid4()

    return Notification.objects.create(
        workspace=workspace,
        project=project,
        sender=sender,
        triggered_by=actor,
        receiver=receiver,
        entity_identifier=issue_id,
        entity_name="issue",
        title="",
        message_stripped=message_stripped,
        data={
            "issue": {
                "id": str(issue_id),
                "name": "修复登录失败",
                "identifier": "PAY",
                "sequence_id": 7,
                "state_name": "进行中",
                "state_group": "started",
            },
            "issue_activity": {
                "id": str(uuid4()),
                "verb": verb,
                "field": field,
                "actor": str(actor.id),
                "new_value": new_value,
                "old_value": old_value,
                "issue_comment": issue_comment,
            },
        },
    )


@pytest.fixture
def enabled_lark(monkeypatch):
    monkeypatch.setattr(
        lark_notifications,
        "get_lark_configuration",
        lambda: SimpleNamespace(
            is_enabled=True,
            notifications_enabled=True,
            public_base_url="https://plane.example",
        ),
    )


@pytest.mark.unit
class TestLarkNotifications:
    @pytest.mark.django_db
    def test_enqueue_builds_structured_state_card(self, enabled_lark):
        notification = _make_notification(old_value="待处理", new_value="进行中")
        Account.objects.create(
            user=notification.receiver,
            provider="lark",
            provider_account_id="on_receiver",
            access_token="",
            metadata={"union_id": "on_receiver"},
        )

        lark_notifications.enqueue_lark_notifications([notification])

        outbox = LarkNotificationOutbox.objects.get(notification=notification)
        card = outbox.payload["card"]
        details = _details(card)
        assert card["summary"] == "张三 更新了状态"
        assert details["任务"] == "PAY-7 修复登录失败"
        assert details["项目"] == "支付系统"
        assert details["触发人"] == "张三"
        assert details["变化"] == "待处理 -> 进行中"
        assert details["当前状态"] == "进行中"

        rendered = _outbox_card(outbox)
        rendered_text = str(rendered)
        assert rendered["header"]["title"]["content"] == "Plane 任务通知"
        assert "待处理 -> 进行中" in rendered_text
        assert "在 Plane 中打开" in rendered_text

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        ("field", "old_value", "new_value", "summary", "change"),
        [
            ("assignees", "", "王五", "张三 添加了负责人", "负责人：王五"),
            ("assignees", "王五", "", "张三 移除了负责人", "负责人：王五"),
            ("labels", "", "缺陷", "张三 添加了标签", "标签：缺陷"),
            ("labels", "缺陷", "", "张三 移除了标签", "标签：缺陷"),
        ],
    )
    def test_structured_card_formats_assignee_and_label_changes(
        self,
        field,
        old_value,
        new_value,
        summary,
        change,
    ):
        notification = _make_notification(field=field, old_value=old_value, new_value=new_value)

        card = lark_notifications._notification_card(notification)

        assert card["summary"] == summary
        assert _details(card)["变化"] == change

    @pytest.mark.django_db
    def test_structured_card_sanitizes_mention_comment(self):
        notification = _make_notification(
            field="comment",
            verb="created",
            new_value=(
                '<p>请看 <strong>这里</strong>'
                '<mention-component label="@李四"></mention-component></p>'
            ),
            sender="in_app:issue_activities:mentioned",
            message_stripped="You have been mentioned in a comment",
        )

        card = lark_notifications._notification_card(notification)
        change = _details(card)["变化"]
        assert card["summary"] == "张三 提及了你"
        assert "请看" in change
        assert "@李四" in change
        assert "<strong>" not in change
        assert "<mention-component" not in change

    @pytest.mark.django_db
    def test_unknown_field_uses_chinese_fallback(self):
        notification = _make_notification(field="custom_score", old_value="1", new_value="2")

        card = lark_notifications._notification_card(notification)

        assert card["summary"] == "张三 更新了custom score"
        assert _details(card)["变化"] == "1 -> 2"

    @pytest.mark.django_db
    def test_legacy_payload_still_renders(self):
        owner = UserFactory(email="owner@example.com", username="owner")
        workspace = WorkspaceFactory(owner=owner)
        outbox = LarkNotificationOutbox.objects.create(
            workspace=workspace,
            recipient_user=owner,
            event_key="notification:legacy:lark",
            message_type="issue_notification",
            payload={
                "title": "旧标题",
                "message": "旧消息",
                "url": "https://plane.example/rd",
            },
        )

        card = _outbox_card(outbox)
        card_text = str(card)

        assert card["header"]["title"]["content"] == "旧标题"
        assert "旧消息" in card_text
        assert "Open in Plane" in card_text

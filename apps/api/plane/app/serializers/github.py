# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from plane.db.models import (
    GithubCredentialProfile,
    GithubManagedRepository,
    GithubRepositoryBranch,
    IssueAgentTask,
)
from plane.license.utils.encryption import encrypt_data

from .base import BaseSerializer


class GithubCredentialProfileSerializer(BaseSerializer):
    token = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = GithubCredentialProfile
        fields = [
            "id",
            "name",
            "provider",
            "token",
            "token_last_four",
            "status",
            "last_verified_at",
            "last_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "provider",
            "token_last_four",
            "status",
            "last_verified_at",
            "last_error",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("token"):
            raise serializers.ValidationError({"token": "Token is required."})
        return attrs

    def create(self, validated_data):
        token = validated_data.pop("token")
        validated_data["token_encrypted"] = encrypt_data(token)
        validated_data["token_last_four"] = token[-4:]
        return GithubCredentialProfile.objects.create(**validated_data)

    def update(self, instance, validated_data):
        token = validated_data.pop("token", None)
        if token:
            instance.token_encrypted = encrypt_data(token)
            instance.token_last_four = token[-4:]
            instance.status = GithubCredentialProfile.Status.ACTIVE
            instance.last_error = None
        return super().update(instance, validated_data)


class GithubManagedRepositorySerializer(BaseSerializer):
    credential_profile_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    branch_count = serializers.SerializerMethodField()

    class Meta:
        model = GithubManagedRepository
        fields = [
            "id",
            "source",
            "credential_profile_id",
            "owner",
            "name",
            "full_name",
            "html_url",
            "default_branch",
            "visibility",
            "sync_status",
            "last_synced_at",
            "last_sync_error",
            "branch_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "default_branch",
            "visibility",
            "sync_status",
            "last_synced_at",
            "last_sync_error",
            "branch_count",
            "created_at",
            "updated_at",
        ]

    def get_branch_count(self, obj):
        if hasattr(obj, "branch_count"):
            return obj.branch_count
        return obj.branches.count()

    def validate(self, attrs):
        source = attrs.get("source", getattr(self.instance, "source", GithubManagedRepository.Source.MANUAL))
        if source == GithubManagedRepository.Source.MANUAL and not attrs.get(
            "credential_profile_id", getattr(self.instance, "credential_profile_id", None)
        ):
            raise serializers.ValidationError({"credential_profile_id": "Credential profile is required."})
        return attrs

    def create(self, validated_data):
        credential_profile_id = validated_data.pop("credential_profile_id", None)
        if credential_profile_id:
            validated_data["credential_profile_id"] = credential_profile_id
        validated_data["full_name"] = f"{validated_data['owner']}/{validated_data['name']}"
        return GithubManagedRepository.objects.create(**validated_data)

    def update(self, instance, validated_data):
        credential_profile_id = validated_data.pop("credential_profile_id", None)
        if credential_profile_id is not None:
            instance.credential_profile_id = credential_profile_id
        if "owner" in validated_data or "name" in validated_data:
            owner = validated_data.get("owner", instance.owner)
            name = validated_data.get("name", instance.name)
            validated_data["full_name"] = f"{owner}/{name}"
        return super().update(instance, validated_data)


class GithubRepositoryBranchSerializer(BaseSerializer):
    class Meta:
        model = GithubRepositoryBranch
        fields = [
            "id",
            "name",
            "sha",
            "protected",
            "is_default",
            "last_seen_at",
        ]
        read_only_fields = fields


class GithubRepositoryLiteSerializer(BaseSerializer):
    class Meta:
        model = GithubManagedRepository
        fields = [
            "id",
            "full_name",
            "html_url",
        ]
        read_only_fields = fields


class IssueAgentTaskSerializer(BaseSerializer):
    repository = GithubRepositoryLiteSerializer(read_only=True)
    repository_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = IssueAgentTask
        fields = [
            "id",
            "status",
            "repository",
            "repository_id",
            "base_branch",
            "work_branch",
            "pr_url",
            "last_error",
            "claimed_by",
            "claimed_at",
            "completed_at",
            "retry_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "repository",
            "work_branch",
            "pr_url",
            "last_error",
            "claimed_by",
            "claimed_at",
            "completed_at",
            "retry_count",
            "created_at",
            "updated_at",
        ]


class IssueAgentTaskLiteSerializer(BaseSerializer):
    repository = GithubRepositoryLiteSerializer(read_only=True)

    class Meta:
        model = IssueAgentTask
        fields = [
            "id",
            "status",
            "repository",
            "base_branch",
            "work_branch",
            "pr_url",
            "last_error",
        ]
        read_only_fields = fields

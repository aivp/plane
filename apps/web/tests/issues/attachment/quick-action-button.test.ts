/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { EIssueServiceType } from "@plane/types";

const dropzoneMocks = vi.hoisted(() => ({
  getInputProps: vi.fn(() => ({ type: "file", multiple: true })),
  getRootProps: vi.fn((props?: Record<string, unknown>) => ({
    ...props,
    "data-attachment-dropzone-root": "true",
  })),
}));

vi.mock("@/hooks/store/use-issue-detail", () => ({
  useIssueDetail: () => ({
    fetchActivities: vi.fn(),
    setLastWidgetAction: vi.fn(),
  }),
}));

vi.mock("../../../core/components/issues/attachment/use-attachment-batch-upload", () => ({
  useAttachmentBatchUpload: () => ({
    getInputProps: dropzoneMocks.getInputProps,
    getRootProps: dropzoneMocks.getRootProps,
    isUploading: false,
  }),
}));

vi.mock("../../../core/components/issues/issue-detail-widgets/attachments/helper", () => ({
  useAttachmentOperations: () => ({
    operations: {
      createMany: vi.fn(),
    },
  }),
}));

import { IssueAttachmentActionButton } from "../../../core/components/issues/issue-detail-widgets/attachments/quick-action-button";

describe("IssueAttachmentActionButton", () => {
  beforeEach(() => {
    dropzoneMocks.getRootProps.mockClear();
  });

  const renderCustomAttachmentButton = () =>
    renderToStaticMarkup(
      React.createElement(IssueAttachmentActionButton, {
        workspaceSlug: "workspace",
        projectId: "project",
        issueId: "issue",
        issueServiceType: EIssueServiceType.ISSUES,
        customButton: React.createElement("button", { type: "button" }, "Attach"),
      })
    );

  test("does not cancel the dropzone click handler", () => {
    renderCustomAttachmentButton();

    expect(dropzoneMocks.getRootProps).toHaveBeenCalledWith();
  });

  test("keeps a custom button out of the dropzone trigger button", () => {
    const markup = renderCustomAttachmentButton();

    expect(markup).not.toMatch(
      /<button[^>]*data-attachment-dropzone-root="true"[^>]*>[\s\S]*<button[^>]*>Attach<\/button>/
    );
  });
});

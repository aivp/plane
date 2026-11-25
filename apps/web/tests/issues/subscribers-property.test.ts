/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";
import { useIssueSubscribers } from "@/hooks/use-issue-subscribers";
import { IssueSubscribersProperty } from "../../core/components/issues/issue-detail/subscribers";

vi.mock("@plane/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@/components/common/layout/sidebar/property-list-item", () => ({
  SidebarPropertyListItem: ({ children }: { children: ReactNode }) => children,
}));
vi.mock("@/components/dropdowns/member/dropdown", () => ({ MemberDropdown: vi.fn(() => null) }));
vi.mock("@/hooks/store/use-member", () => ({
  useMember: () => ({ project: { getProjectMemberIds: () => ["member", "new-member"] } }),
}));
vi.mock("@/hooks/use-issue-subscribers", () => ({ useIssueSubscribers: vi.fn() }));

const state = {
  subscriberIds: ["member"],
  isLoading: false,
  isUpdating: false,
  error: undefined,
  retry: vi.fn(),
  setSubscriberIds: vi.fn(),
};

const renderProperty = (disabled = false) =>
  renderToStaticMarkup(
    createElement(IssueSubscribersProperty, { workspaceSlug: "w", projectId: "p", issueId: "i", disabled })
  );

describe("work item subscribers property", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useIssueSubscribers).mockReturnValue(state);
  });

  test("offers project members for addition and keeps a previous subscriber available for removal", () => {
    vi.mocked(useIssueSubscribers).mockReturnValue({ ...state, subscriberIds: ["member", "former-member-now-guest"] });
    renderProperty();
    expect(vi.mocked(MemberDropdown).mock.lastCall?.[0]).toMatchObject({
      multiple: true,
      projectId: "p",
      memberIds: ["member", "new-member", "former-member-now-guest"],
      value: ["member", "former-member-now-guest"],
      disabled: false,
      onChange: state.setSubscriberIds,
    });
  });

  test("shows current subscribers but disables editing for a read-only work item or pending update", () => {
    renderProperty(true);
    expect(vi.mocked(MemberDropdown).mock.lastCall?.[0]).toMatchObject({ value: ["member"], disabled: true });

    vi.mocked(useIssueSubscribers).mockReturnValue({ ...state, isUpdating: true });
    renderProperty();
    expect(vi.mocked(MemberDropdown).mock.lastCall?.[0]).toMatchObject({ value: ["member"], disabled: true });
  });

  test("waits for the subscriber list and offers a retry on failure", () => {
    vi.mocked(useIssueSubscribers).mockReturnValue({ ...state, subscriberIds: undefined, isLoading: true });
    expect(renderProperty()).toContain("common.loading");
    expect(MemberDropdown).not.toHaveBeenCalled();

    vi.mocked(useIssueSubscribers).mockReturnValue({ ...state, error: new Error("unavailable") });
    expect(renderProperty()).toContain("common.retry");
    expect(MemberDropdown).not.toHaveBeenCalled();
  });
});

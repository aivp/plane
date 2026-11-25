/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Bell } from "lucide-react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";
import { useMember } from "@/hooks/store/use-member";
import { useIssueSubscribers } from "@/hooks/use-issue-subscribers";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
};

export const IssueSubscribersProperty = observer(function IssueSubscribersProperty({
  workspaceSlug,
  projectId,
  issueId,
  disabled,
}: Props) {
  const { t } = useTranslation();
  const { project } = useMember();
  const { subscriberIds, isLoading, isUpdating, error, retry, setSubscriberIds } = useIssueSubscribers(
    workspaceSlug,
    projectId,
    issueId
  );
  const label = t("issue.subscription.subscribers");
  const projectMemberIds = project.getProjectMemberIds(projectId, false);
  // An existing subscriber may since have become a guest. Keep them selectable for removal.
  const memberIds =
    projectMemberIds && subscriberIds ? [...new Set([...projectMemberIds, ...subscriberIds])] : undefined;

  return (
    <SidebarPropertyListItem icon={Bell} label={label}>
      {error ? (
        <div className="flex min-h-7.5 flex-wrap items-center gap-x-2 px-2 text-body-xs-regular">
          <span className="text-secondary">{t("entity.fetch.failed", { entity: label })}</span>
          <button type="button" className="text-link-primary" onClick={retry}>
            {t("common.retry")}
          </button>
        </div>
      ) : isLoading || !subscriberIds ? (
        <span role="status" className="flex h-7.5 items-center px-2 text-body-xs-regular text-placeholder">
          {t("common.loading")}
        </span>
      ) : (
        <MemberDropdown
          value={subscriberIds}
          onChange={setSubscriberIds}
          disabled={disabled || isUpdating}
          memberIds={memberIds}
          projectId={projectId}
          placeholder={disabled ? t("common.none") : t("issue.subscription.add_subscribers")}
          multiple
          buttonVariant={subscriberIds.length > 1 ? "transparent-without-text" : "transparent-with-text"}
          className="group w-full grow"
          buttonContainerClassName="w-full text-left h-7.5"
          buttonClassName={cn("justify-between text-body-xs-regular", !subscriberIds.length && "text-placeholder")}
          hideIcon={!subscriberIds.length}
          dropdownArrow={!disabled}
          dropdownArrowClassName="h-3.5 w-3.5 hidden group-hover:inline"
        />
      )}
    </SidebarPropertyListItem>
  );
});

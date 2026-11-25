/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import useSWR from "swr";
import useSWRMutation from "swr/mutation";
import { useTranslation } from "@plane/i18n";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { IssueService } from "@/services/issue/issue.service";

const issueService = new IssueService();

export function useIssueSubscribers(workspaceSlug: string, projectId: string, issueId: string) {
  const { t } = useTranslation();
  const { subscription, rootIssueStore } = useIssueDetail();
  const currentUserId = rootIssueStore.currentUserId;
  const key = issueService.subscriberIdsUrl(workspaceSlug, projectId, issueId);
  const {
    data: subscriberIds,
    error,
    isLoading,
    mutate,
  } = useSWR(key, () => issueService.getSubscriberIds(workspaceSlug, projectId, issueId));
  const { trigger, isMutating } = useSWRMutation(
    key,
    async (_key, { arg }: { arg: { previousIds: string[]; selectedIds: string[] } }) => {
      await issueService.updateSubscribers(workspaceSlug, projectId, issueId, arg.previousIds, arg.selectedIds);
      return arg.selectedIds;
    },
    {
      populateCache: true,
      throwOnError: false,
      onError: () =>
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("toast.error"),
          message: t("entity.update.failed", { entity: t("issue.subscription.subscribers") }),
        }),
    }
  );

  useEffect(() => {
    if (subscriberIds && currentUserId) subscription.addSubscription(issueId, subscriberIds.includes(currentUserId));
  }, [subscription, issueId, currentUserId, subscriberIds]);

  async function setSubscriberIds(selectedIds: string[]) {
    if (!subscriberIds || error || isMutating) return;
    await trigger({ previousIds: subscriberIds, selectedIds }, { optimisticData: selectedIds });
  }

  return { subscriberIds, error, isLoading, isUpdating: isMutating, setSubscriberIds, retry: () => void mutate() };
}

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useState } from "react";
import { isEqual, cloneDeep } from "lodash-es";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { DEFAULT_GLOBAL_VIEWS_LIST, EUserPermissionsLevel, WORKSPACE_CYCLES } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import type { IWorkspaceView, TWorkItemFilterExpression } from "@plane/types";
import { EUserProjectRoles, EViewAccess } from "@plane/types";
// components
import { removeNillKeys } from "@/components/issues/issue-layouts/utils";
import { CreateUpdateWorkspaceViewModal } from "@/components/workspace/views/modal";
// hooks
import { useCycle } from "@/hooks/store/use-cycle";
import { useGlobalView } from "@/hooks/store/use-global-view";
import { useLabel } from "@/hooks/store/use-label";
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { useUser, useUserPermissions } from "@/hooks/store/user";
// local imports
import { WorkItemFiltersHOC } from "./base";
import type { TEnableSaveViewProps, TEnableUpdateViewProps, TSharedWorkItemFiltersHOCProps } from "./shared";

type TWorkspaceLevelWorkItemFiltersHOCProps = TSharedWorkItemFiltersHOCProps & {
  workspaceSlug: string;
} & TEnableSaveViewProps &
  TEnableUpdateViewProps;

export const WorkspaceLevelWorkItemFiltersHOC = observer(function WorkspaceLevelWorkItemFiltersHOC(
  props: TWorkspaceLevelWorkItemFiltersHOCProps
) {
  const { children, enableSaveView, enableUpdateView, entityId, initialWorkItemFilters, workspaceSlug } = props;
  // states
  const [isCreateViewModalOpen, setIsCreateViewModalOpen] = useState(false);
  const [createViewPayload, setCreateViewPayload] = useState<Partial<IWorkspaceView> | undefined>(undefined);
  // hooks
  const { getViewDetailsById, updateGlobalView } = useGlobalView();
  const { data: currentUser } = useUser();
  const { allowPermissions } = useUserPermissions();
  const { t } = useTranslation();
  const { joinedProjectIds, getProjectById } = useProject();
  const { cycleMap, fetchWorkspaceCycles } = useCycle();
  const {
    workspace: { getWorkspaceMemberIds },
  } = useMember();
  const { getWorkspaceLabelIds } = useLabel();
  // derived values
  const hasWorkspaceMemberLevelPermissions = allowPermissions(
    [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
    EUserPermissionsLevel.WORKSPACE,
    workspaceSlug
  );
  const viewDetails = entityId ? getViewDetailsById(entityId) : null;
  const isDefaultView = typeof entityId === "string" && DEFAULT_GLOBAL_VIEWS_LIST.some((view) => view.key === entityId);
  const isViewLocked = viewDetails ? viewDetails?.is_locked : false;
  const isCurrentUserOwner = viewDetails ? viewDetails.owned_by === currentUser?.id : false;
  const shouldLoadWorkspaceCycles = props.filtersToShowByLayout.includes("cycle_id");
  const joinedProjectOrder = new Map(joinedProjectIds.map((projectId, index) => [projectId, index]));
  const workspaceCycleIds = shouldLoadWorkspaceCycles
    ? Object.values(cycleMap ?? {})
        .filter((cycle) => {
          const project = getProjectById(cycle.project_id);
          return (
            joinedProjectOrder.has(cycle.project_id) &&
            !cycle.archived_at &&
            project?.cycle_view === true &&
            !project?.archived_at
          );
        })
        .sort((a, b) => {
          const projectSortOrder =
            (joinedProjectOrder.get(a.project_id) ?? Number.MAX_SAFE_INTEGER) -
            (joinedProjectOrder.get(b.project_id) ?? Number.MAX_SAFE_INTEGER);
          if (projectSortOrder !== 0) return projectSortOrder;
          return a.sort_order - b.sort_order;
        })
        .map((cycle) => cycle.id)
    : undefined;

  useSWR(
    shouldLoadWorkspaceCycles ? WORKSPACE_CYCLES(workspaceSlug) : null,
    () => fetchWorkspaceCycles(workspaceSlug),
    {
      revalidateIfStale: false,
      revalidateOnFocus: false,
    }
  );

  const canCreateView = useMemo(
    () => enableSaveView && !props.saveViewOptions?.isDisabled && hasWorkspaceMemberLevelPermissions,
    [enableSaveView, props.saveViewOptions?.isDisabled, hasWorkspaceMemberLevelPermissions]
  );
  const canUpdateView = useMemo(
    () =>
      enableUpdateView &&
      !isDefaultView &&
      !props.updateViewOptions?.isDisabled &&
      !isViewLocked &&
      hasWorkspaceMemberLevelPermissions &&
      isCurrentUserOwner,
    [
      enableUpdateView,
      props.updateViewOptions?.isDisabled,
      isDefaultView,
      isViewLocked,
      hasWorkspaceMemberLevelPermissions,
      isCurrentUserOwner,
    ]
  );
  const createViewLabel = useMemo(() => props.saveViewOptions?.label, [props.saveViewOptions?.label]);
  const updateViewLabel = useMemo(() => props.updateViewOptions?.label, [props.updateViewOptions?.label]);
  const hasAdditionalChanges = useMemo(
    () =>
      !isEqual(initialWorkItemFilters?.displayFilters, viewDetails?.display_filters) ||
      !isEqual(
        removeNillKeys(initialWorkItemFilters?.displayProperties),
        removeNillKeys(viewDetails?.display_properties)
      ),
    [initialWorkItemFilters, viewDetails]
  );

  const getDefaultViewDetailPayload: () => Partial<IWorkspaceView> = useCallback(
    () => ({
      name: viewDetails ? `${viewDetails?.name} 2` : t("view.untitled"),
      description: viewDetails ? viewDetails.description : "",
      access: viewDetails ? viewDetails.access : EViewAccess.PUBLIC,
    }),
    [viewDetails, t]
  );

  const getViewFilterPayload: (filterExpression: TWorkItemFilterExpression) => Partial<IWorkspaceView> = useCallback(
    (filterExpression: TWorkItemFilterExpression) => ({
      rich_filters: cloneDeep(filterExpression),
      display_filters: cloneDeep(initialWorkItemFilters?.displayFilters),
      display_properties: cloneDeep(initialWorkItemFilters?.displayProperties),
    }),
    [initialWorkItemFilters]
  );

  const handleViewSave = useCallback(
    (expression: TWorkItemFilterExpression) => {
      setCreateViewPayload({
        ...getDefaultViewDetailPayload(),
        ...getViewFilterPayload(expression),
      });
      setIsCreateViewModalOpen(true);
    },
    [getDefaultViewDetailPayload, getViewFilterPayload]
  );

  const handleViewUpdate = useCallback(
    (filterExpression: TWorkItemFilterExpression) => {
      if (!viewDetails) {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("view.not_found.title"),
          message: t("view.not_found.message"),
        });

        return;
      }

      updateGlobalView(
        workspaceSlug,
        viewDetails.id,
        {
          ...getViewFilterPayload(filterExpression),
        },
        /* No need to sync filters here as updateFilters already handles it */
        false
      )
        .then(() => {
          setToast({
            type: TOAST_TYPE.SUCCESS,
            title: t("common.success"),
            message: t("view.updated.success"),
          });
        })
        .catch(() => {
          setToast({
            type: TOAST_TYPE.ERROR,
            title: t("common.error.label"),
            message: t("view.updated.error"),
          });
        });
    },
    [viewDetails, updateGlobalView, workspaceSlug, getViewFilterPayload, t]
  );

  const saveViewOptions = useMemo(
    () => ({
      label: createViewLabel,
      isDisabled: !canCreateView,
      onViewSave: handleViewSave,
    }),
    [createViewLabel, canCreateView, handleViewSave]
  );

  const updateViewOptions = useMemo(
    () => ({
      label: updateViewLabel,
      isDisabled: !canUpdateView,
      hasAdditionalChanges,
      onViewUpdate: handleViewUpdate,
    }),
    [updateViewLabel, canUpdateView, hasAdditionalChanges, handleViewUpdate]
  );

  return (
    <>
      <CreateUpdateWorkspaceViewModal
        preLoadedData={createViewPayload}
        isOpen={isCreateViewModalOpen}
        onClose={() => {
          setCreateViewPayload(undefined);
          setIsCreateViewModalOpen(false);
        }}
      />
      <WorkItemFiltersHOC
        {...props}
        memberIds={getWorkspaceMemberIds(workspaceSlug)}
        labelIds={getWorkspaceLabelIds(workspaceSlug)}
        projectIds={joinedProjectIds}
        cycleIds={workspaceCycleIds}
        saveViewOptions={saveViewOptions}
        updateViewOptions={updateViewOptions}
      >
        {children}
      </WorkItemFiltersHOC>
    </>
  );
});

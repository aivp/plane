/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useCallback } from "react";
import { observer } from "mobx-react";
import { PlusIcon } from "@plane/propel/icons";
import type { TIssueServiceType } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// local imports
import { useAttachmentBatchUpload } from "../../attachment/use-attachment-batch-upload";
import { useAttachmentOperations } from "./helper";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  customButton?: React.ReactNode;
  disabled?: boolean;
  issueServiceType: TIssueServiceType;
};

export const IssueAttachmentActionButton = observer(function IssueAttachmentActionButton(props: Props) {
  const { workspaceSlug, projectId, issueId, customButton, disabled = false, issueServiceType } = props;
  // store hooks
  const { setLastWidgetAction, fetchActivities } = useIssueDetail(issueServiceType);
  // operations
  const { operations: attachmentOperations } = useAttachmentOperations(
    workspaceSlug,
    projectId,
    issueId,
    issueServiceType
  );
  // handlers
  const handleFetchPropertyActivities = useCallback(() => {
    fetchActivities(workspaceSlug, projectId, issueId);
    setLastWidgetAction("attachments");
  }, [fetchActivities, issueId, projectId, setLastWidgetAction, workspaceSlug]);

  const { getRootProps, getInputProps, isUploading } = useAttachmentBatchUpload({
    attachmentOperations,
    disabled,
    onUploadSettled: handleFetchPropertyActivities,
  });

  const trigger = customButton ? (
    <div {...getRootProps()} className="contents">
      <input {...getInputProps()} />
      {customButton}
    </div>
  ) : (
    <button {...getRootProps()} type="button" disabled={disabled || isUploading}>
      <input {...getInputProps()} />
      <PlusIcon className="h-4 w-4" />
    </button>
  );

  return (
    // The dropzone click must run before propagation is stopped. Keeping this
    // wrapper outside the dropzone also prevents custom buttons from nesting.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div
      className="contents"
      onClick={(event) => {
        event.stopPropagation();
      }}
    >
      {trigger}
    </div>
  );
});

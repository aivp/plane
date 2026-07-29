/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { observer } from "mobx-react";
import { UploadCloud } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import type { TIssueAttachment, TIssueServiceType } from "@plane/types";
import { EIssueServiceType } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// types
import type { TAttachmentHelpers } from "../issue-detail-widgets/attachments/helper";
// components
import { IssueAttachmentsListItem } from "./attachment-list-item";
import { IssueAttachmentsUploadItem } from "./attachment-list-upload-item";
import { isAttachmentPreviewable } from "./helpers";
import { IssueAttachmentMediaPreviewModal } from "./media-preview-modal";
// types
import { IssueAttachmentDeleteModal } from "./delete-attachment-modal";
import { useAttachmentBatchUpload } from "./use-attachment-batch-upload";

type TIssueAttachmentItemList = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  attachmentHelpers: TAttachmentHelpers;
  disabled?: boolean;
  issueServiceType?: TIssueServiceType;
};

export const IssueAttachmentItemList = observer(function IssueAttachmentItemList(props: TIssueAttachmentItemList) {
  const {
    workspaceSlug,
    projectId,
    issueId,
    attachmentHelpers,
    disabled,
    issueServiceType = EIssueServiceType.ISSUES,
  } = props;
  const { t } = useTranslation();
  // states
  const [previewAttachmentId, setPreviewAttachmentId] = useState<string | null>(null);
  // store hooks
  const {
    attachment: { getAttachmentById, getAttachmentsByIssueId },
    attachmentDeleteModalId,
    toggleDeleteAttachmentModal,
    fetchActivities,
  } = useIssueDetail(issueServiceType);
  const { operations: attachmentOperations, snapshot: attachmentSnapshot } = attachmentHelpers;
  const { uploadStatus } = attachmentSnapshot;
  // derived values
  const issueAttachments = getAttachmentsByIssueId(issueId);
  const previewableAttachments =
    issueAttachments
      ?.map((attachmentId) => getAttachmentById(attachmentId))
      .filter((attachment): attachment is TIssueAttachment => !!attachment && isAttachmentPreviewable(attachment)) ??
    [];

  // handlers
  const handleFetchPropertyActivities = useCallback(() => {
    fetchActivities(workspaceSlug, projectId, issueId);
  }, [fetchActivities, workspaceSlug, projectId, issueId]);

  const { getRootProps, getInputProps, isDragActive, isUploading } = useAttachmentBatchUpload({
    attachmentOperations,
    disabled,
    onUploadSettled: handleFetchPropertyActivities,
  });

  return (
    <>
      {uploadStatus?.map((currentUploadStatus) => (
        <IssueAttachmentsUploadItem key={currentUploadStatus.id} uploadStatus={currentUploadStatus} />
      ))}
      {issueAttachments && (
        <>
          <IssueAttachmentMediaPreviewModal
            activeAttachmentId={previewAttachmentId}
            attachments={previewableAttachments}
            fetchHtmlPreview={attachmentOperations.fetchHtmlPreview}
            isOpen={!!previewAttachmentId}
            onActiveAttachmentIdChange={setPreviewAttachmentId}
            onClose={() => setPreviewAttachmentId(null)}
          />
          {attachmentDeleteModalId && (
            <IssueAttachmentDeleteModal
              isOpen={Boolean(attachmentDeleteModalId)}
              onClose={() => toggleDeleteAttachmentModal(null)}
              attachmentOperations={attachmentOperations}
              attachmentId={attachmentDeleteModalId}
              issueServiceType={issueServiceType}
            />
          )}
          <div
            {...getRootProps()}
            className={`relative flex flex-col ${isDragActive && issueAttachments.length < 3 ? "min-h-[200px]" : ""} ${
              disabled || isUploading ? "cursor-not-allowed" : "cursor-pointer"
            }`}
          >
            <input {...getInputProps()} />
            {isDragActive && (
              <div className="absolute top-0 left-0 z-30 flex h-full w-full items-center justify-center bg-surface-2/75">
                <div className="flex items-center justify-center rounded-md bg-surface-1 p-1">
                  <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-strong px-5 py-6">
                    <UploadCloud className="size-7" />
                    <span className="text-13 text-tertiary">{t("attachment.drag_and_drop")}</span>
                  </div>
                </div>
              </div>
            )}
            {issueAttachments?.map((attachmentId) => (
              <IssueAttachmentsListItem
                key={attachmentId}
                attachmentId={attachmentId}
                disabled={disabled}
                issueServiceType={issueServiceType}
                onPreviewAttachment={setPreviewAttachmentId}
              />
            ))}
          </div>
        </>
      )}
    </>
  );
});

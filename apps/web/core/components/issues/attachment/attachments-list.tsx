/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import type { TIssueAttachment } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// types
import type { TAttachmentHelpers } from "../issue-detail-widgets/attachments/helper";
// components
import { IssueAttachmentsDetail } from "./attachment-detail";
import { IssueAttachmentsUploadDetails } from "./attachment-upload-details";
import { isAttachmentPreviewable } from "./helpers";
import { IssueAttachmentMediaPreviewModal } from "./media-preview-modal";

type TIssueAttachmentsList = {
  issueId: string;
  attachmentHelpers: TAttachmentHelpers;
  disabled?: boolean;
};

export const IssueAttachmentsList = observer(function IssueAttachmentsList(props: TIssueAttachmentsList) {
  const { issueId, attachmentHelpers, disabled } = props;
  const [previewAttachmentId, setPreviewAttachmentId] = useState<string | null>(null);
  // store hooks
  const {
    attachment: { getAttachmentById, getAttachmentsByIssueId },
  } = useIssueDetail();
  // derived values
  const { snapshot: attachmentSnapshot } = attachmentHelpers;
  const { uploadStatus } = attachmentSnapshot;
  const issueAttachments = getAttachmentsByIssueId(issueId);
  const previewableAttachments =
    issueAttachments
      ?.map((attachmentId) => getAttachmentById(attachmentId))
      .filter((attachment): attachment is TIssueAttachment => !!attachment && isAttachmentPreviewable(attachment)) ??
    [];

  return (
    <>
      <IssueAttachmentMediaPreviewModal
        activeAttachmentId={previewAttachmentId}
        attachments={previewableAttachments}
        fetchHtmlPreview={attachmentHelpers.operations.fetchHtmlPreview}
        isOpen={!!previewAttachmentId}
        onActiveAttachmentIdChange={setPreviewAttachmentId}
        onClose={() => setPreviewAttachmentId(null)}
      />
      {uploadStatus?.map((currentUploadStatus) => (
        <IssueAttachmentsUploadDetails key={currentUploadStatus.id} uploadStatus={currentUploadStatus} />
      ))}
      {issueAttachments?.map((attachmentId) => (
        <IssueAttachmentsDetail
          key={attachmentId}
          attachmentId={attachmentId}
          disabled={disabled}
          attachmentHelpers={attachmentHelpers}
          onPreviewAttachment={setPreviewAttachmentId}
        />
      ))}
    </>
  );
});

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MouseEvent } from "react";
import { useState } from "react";
import { observer } from "mobx-react";
import { AlertCircle, Download } from "lucide-react";
import { CloseIcon } from "@plane/propel/icons";
import { IconButton } from "@plane/propel/icon-button";
// ui
import { Tooltip } from "@plane/propel/tooltip";
import { convertBytesToSize, renderFormattedDate, truncateText } from "@plane/utils";
// icons
//
import { getFileIcon } from "@/components/icons";
// components
import { IssueAttachmentDeleteModal } from "@/components/issues/attachment/delete-attachment-modal";
// helpers
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useMember } from "@/hooks/store/use-member";
import { usePlatformOS } from "@/hooks/use-platform-os";
// types
import type { TAttachmentHelpers } from "../issue-detail-widgets/attachments/helper";
import { getAttachmentDisplayName, getAttachmentExtension, getAttachmentURL, isAttachmentPreviewable } from "./helpers";

type TAttachmentOperationsRemoveModal = Exclude<TAttachmentHelpers, "create">;

type TIssueAttachmentsDetail = {
  attachmentId: string;
  attachmentHelpers: TAttachmentOperationsRemoveModal;
  disabled?: boolean;
  onPreviewAttachment?: (attachmentId: string) => void;
};

export const IssueAttachmentsDetail = observer(function IssueAttachmentsDetail(props: TIssueAttachmentsDetail) {
  // props
  const { attachmentId, attachmentHelpers, disabled, onPreviewAttachment } = props;
  // store hooks
  const { getUserDetails } = useMember();
  const {
    attachment: { getAttachmentById },
  } = useIssueDetail();
  // state
  const [isDeleteIssueAttachmentModalOpen, setIsDeleteIssueAttachmentModalOpen] = useState(false);
  // derived values
  const attachment = attachmentId ? getAttachmentById(attachmentId) : undefined;
  const fileName = attachment ? getAttachmentDisplayName(attachment) : "";
  const fileExtension = attachment ? getAttachmentExtension(attachment) : "";
  const fileIcon = getFileIcon(fileExtension, 28);
  const isPreviewable = attachment ? isAttachmentPreviewable(attachment) : false;
  // hooks
  const { isMobile } = usePlatformOS();

  if (!attachment) return <></>;

  const handlePreview = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (!isPreviewable) return;
    onPreviewAttachment?.(attachmentId);
  };

  const handleDownload = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const downloadURL = getAttachmentURL(attachment, "attachment");
    if (!downloadURL) return;
    window.open(downloadURL, "_blank", "noopener,noreferrer");
  };

  const handleDelete = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDeleteIssueAttachmentModalOpen(true);
  };

  return (
    <>
      {isDeleteIssueAttachmentModalOpen && (
        <IssueAttachmentDeleteModal
          isOpen={isDeleteIssueAttachmentModalOpen}
          onClose={() => setIsDeleteIssueAttachmentModalOpen(false)}
          attachmentOperations={attachmentHelpers.operations}
          attachmentId={attachmentId}
        />
      )}
      <div className="flex h-[60px] items-center justify-between gap-1 rounded-md border-[2px] border-subtle bg-surface-1 px-4 py-2 text-13">
        <button
          type="button"
          aria-disabled={!isPreviewable}
          aria-label={isPreviewable ? `Preview ${fileName}` : undefined}
          className={`flex min-w-0 flex-1 items-center gap-3 text-left ${isPreviewable ? "cursor-pointer" : "cursor-default"}`}
          onClick={handlePreview}
          tabIndex={isPreviewable ? 0 : -1}
        >
          <div className="h-7 w-7 flex-shrink-0">{fileIcon}</div>
          <div className="flex min-w-0 flex-col gap-1">
            <div className="flex min-w-0 items-center gap-2">
              <Tooltip tooltipContent={fileName} isMobile={isMobile}>
                <span className="truncate text-13">{truncateText(fileName, 10)}</span>
              </Tooltip>
              <Tooltip
                isMobile={isMobile}
                tooltipContent={`${
                  getUserDetails(attachment.updated_by)?.display_name ?? ""
                } uploaded on ${renderFormattedDate(attachment.updated_at)}`}
              >
                <span className="flex-shrink-0">
                  <AlertCircle className="h-3 w-3" />
                </span>
              </Tooltip>
            </div>

            <div className="flex items-center gap-3 text-11 text-secondary">
              {fileExtension && <span>{fileExtension.toUpperCase()}</span>}
              <span>{convertBytesToSize(attachment.attributes.size)}</span>
            </div>
          </div>
        </button>

        <Tooltip tooltipContent="Download" isMobile={isMobile}>
          <IconButton
            aria-label="Download attachment"
            icon={Download}
            size="base"
            variant="ghost"
            onClick={handleDownload}
          />
        </Tooltip>
        {!disabled && (
          <button type="button" onClick={handleDelete}>
            <CloseIcon className="h-4 w-4 text-secondary hover:text-primary" />
          </button>
        )}
      </div>
    </>
  );
});

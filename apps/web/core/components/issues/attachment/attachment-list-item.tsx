/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MouseEvent } from "react";
import { observer } from "mobx-react";

import { Download } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { TrashIcon } from "@plane/propel/icons";
import { IconButton } from "@plane/propel/icon-button";
import { Tooltip } from "@plane/propel/tooltip";
import type { TIssueServiceType } from "@plane/types";
import { EIssueServiceType } from "@plane/types";
// ui
import { CustomMenu } from "@plane/ui";
import { convertBytesToSize, renderFormattedDate } from "@plane/utils";
// components
//
import { ButtonAvatars } from "@/components/dropdowns/member/avatar";
import { getFileIcon } from "@/components/icons";
// helpers
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useMember } from "@/hooks/store/use-member";
import { usePlatformOS } from "@/hooks/use-platform-os";
import { getAttachmentDisplayName, getAttachmentExtension, getAttachmentURL, isAttachmentPreviewable } from "./helpers";

type TIssueAttachmentsListItem = {
  attachmentId: string;
  disabled?: boolean;
  issueServiceType?: TIssueServiceType;
  onPreviewAttachment?: (attachmentId: string) => void;
};

export const IssueAttachmentsListItem = observer(function IssueAttachmentsListItem(props: TIssueAttachmentsListItem) {
  const { t } = useTranslation();
  // props
  const { attachmentId, disabled, issueServiceType = EIssueServiceType.ISSUES, onPreviewAttachment } = props;
  // store hooks
  const { getUserDetails } = useMember();
  const {
    attachment: { getAttachmentById },
    toggleDeleteAttachmentModal,
  } = useIssueDetail(issueServiceType);
  // derived values
  const attachment = attachmentId ? getAttachmentById(attachmentId) : undefined;
  const fileName = attachment ? getAttachmentDisplayName(attachment) : "";
  const fileExtension = attachment ? getAttachmentExtension(attachment) : "";
  const fileIcon = getFileIcon(fileExtension, 18);
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

  return (
    <>
      <div className="group flex h-11 items-center justify-between gap-3 pr-2 pl-9 hover:bg-surface-2">
        <button
          type="button"
          aria-disabled={!isPreviewable}
          aria-label={isPreviewable ? `Preview ${fileName}` : undefined}
          className={`flex min-w-0 flex-1 items-center gap-3 truncate text-left text-13 ${isPreviewable ? "cursor-pointer" : "cursor-default"}`}
          onClick={handlePreview}
          tabIndex={isPreviewable ? 0 : -1}
        >
          <div className="flex flex-shrink-0 items-center gap-3">{fileIcon}</div>
          <Tooltip tooltipContent={fileName} isMobile={isMobile}>
            <p className="truncate font-medium text-secondary">{fileName}</p>
          </Tooltip>
          <span className="flex size-1.5 flex-shrink-0 rounded-full bg-layer-1" />
          <span className="flex-shrink-0 text-placeholder">{convertBytesToSize(attachment.attributes.size)}</span>
        </button>

        <div className="flex items-center gap-3">
          {attachment?.created_by && (
            <Tooltip
              isMobile={isMobile}
              tooltipContent={`${
                getUserDetails(attachment?.created_by)?.display_name ?? ""
              } uploaded on ${renderFormattedDate(attachment.updated_at)}`}
            >
              <div className="flex items-center justify-center">
                <ButtonAvatars showTooltip userIds={attachment?.created_by} />
              </div>
            </Tooltip>
          )}

          <Tooltip tooltipContent="Download" isMobile={isMobile}>
            <IconButton
              aria-label="Download attachment"
              icon={Download}
              size="base"
              variant="ghost"
              onClick={handleDownload}
            />
          </Tooltip>

          <CustomMenu ellipsis closeOnSelect placement="bottom-end" disabled={disabled}>
            <CustomMenu.MenuItem
              onClick={() => {
                toggleDeleteAttachmentModal(attachmentId);
              }}
            >
              <div className="flex items-center gap-2">
                <TrashIcon className="h-3.5 w-3.5" strokeWidth={2} />
                <span>{t("common.actions.delete")}</span>
              </div>
            </CustomMenu.MenuItem>
          </CustomMenu>
        </div>
      </div>
    </>
  );
});

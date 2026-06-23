/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo } from "react";
import { ChevronLeft, ChevronRight, Download, X } from "lucide-react";
import { Dialog, EDialogWidth } from "@plane/propel/dialog";
import { IconButton } from "@plane/propel/icon-button";
import { Tooltip } from "@plane/propel/tooltip";
import type { TIssueAttachment } from "@plane/types";
// local imports
import { getAttachmentDisplayName, getAttachmentMediaType, getAttachmentURL } from "./helpers";

type TIssueAttachmentMediaPreviewModal = {
  activeAttachmentId: string | null;
  attachments: TIssueAttachment[];
  isOpen: boolean;
  onActiveAttachmentIdChange: (attachmentId: string) => void;
  onClose: () => void;
};

export function IssueAttachmentMediaPreviewModal(props: TIssueAttachmentMediaPreviewModal) {
  const { activeAttachmentId, attachments, isOpen, onActiveAttachmentIdChange, onClose } = props;

  const activeIndex = useMemo(
    () => attachments.findIndex((attachment) => attachment.id === activeAttachmentId),
    [activeAttachmentId, attachments]
  );
  const activeAttachment = activeIndex >= 0 ? attachments[activeIndex] : undefined;
  const activeMediaType = activeAttachment ? getAttachmentMediaType(activeAttachment) : undefined;
  const canNavigate = attachments.length > 1;

  const movePreview = useCallback(
    (direction: -1 | 1) => {
      if (!canNavigate || activeIndex < 0) return;
      const nextIndex = (activeIndex + direction + attachments.length) % attachments.length;
      onActiveAttachmentIdChange(attachments[nextIndex].id);
    },
    [activeIndex, attachments, canNavigate, onActiveAttachmentIdChange]
  );

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }

      if (event.key === "ArrowLeft") {
        event.preventDefault();
        movePreview(-1);
      }

      if (event.key === "ArrowRight") {
        event.preventDefault();
        movePreview(1);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, movePreview, onClose]);

  if (!activeAttachment || !activeMediaType) return null;

  const fileName = getAttachmentDisplayName(activeAttachment);
  const previewURL = getAttachmentURL(activeAttachment, "inline");
  const downloadURL = getAttachmentURL(activeAttachment, "attachment");

  const handleDownload = () => {
    if (!downloadURL) return;
    window.open(downloadURL, "_blank", "noopener,noreferrer");
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Panel
        width={EDialogWidth.VIIXL}
        className="flex h-[min(86vh,760px)] max-h-[86vh] w-[min(94vw,1120px)] max-w-none flex-col overflow-hidden"
      >
        <div className="flex h-12 flex-shrink-0 items-center justify-between gap-3 border-b border-subtle px-4">
          <Dialog.Title className="truncate text-14 font-medium">{fileName}</Dialog.Title>
          <div className="flex flex-shrink-0 items-center gap-1">
            <Tooltip tooltipContent="Download">
              <IconButton
                aria-label="Download attachment"
                icon={Download}
                size="base"
                variant="ghost"
                onClick={handleDownload}
              />
            </Tooltip>
            <Tooltip tooltipContent="Close">
              <IconButton aria-label="Close preview" icon={X} size="base" variant="ghost" onClick={onClose} />
            </Tooltip>
          </div>
        </div>

        <div className="relative flex min-h-0 flex-1 items-center justify-center bg-surface-2 p-4">
          {canNavigate && (
            <Tooltip tooltipContent="Previous attachment">
              <IconButton
                aria-label="Previous attachment"
                className="absolute left-4 z-10 bg-surface-1/90 shadow-raised-100"
                icon={ChevronLeft}
                size="xl"
                variant="secondary"
                onClick={() => movePreview(-1)}
              />
            </Tooltip>
          )}

          {previewURL &&
            (activeMediaType === "image" ? (
              <img alt={fileName} className="max-h-full max-w-full object-contain" src={previewURL} />
            ) : (
              <video
                key={activeAttachment.id}
                className="max-h-full max-w-full"
                controls
                preload="metadata"
                src={previewURL}
              >
                <track kind="captions" />
              </video>
            ))}

          {canNavigate && (
            <Tooltip tooltipContent="Next attachment">
              <IconButton
                aria-label="Next attachment"
                className="absolute right-4 z-10 bg-surface-1/90 shadow-raised-100"
                icon={ChevronRight}
                size="xl"
                variant="secondary"
                onClick={() => movePreview(1)}
              />
            </Tooltip>
          )}
        </div>
      </Dialog.Panel>
    </Dialog>
  );
}

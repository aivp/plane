/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type SyntheticEvent } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, Download, LoaderCircle, X } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { Dialog, EDialogWidth } from "@plane/propel/dialog";
import { IconButton } from "@plane/propel/icon-button";
import { Tooltip } from "@plane/propel/tooltip";
import type { TIssueAttachment } from "@plane/types";
// local imports
import { getAttachmentDisplayName, getAttachmentPreviewType, getAttachmentURL } from "./helpers";
import { buildSandboxedHtmlPreviewDocument } from "./html-preview";

type THtmlPreviewState = { status: "loading" } | { status: "success"; content: string } | { status: "error" };

type TIssueAttachmentMediaPreviewModal = {
  activeAttachmentId: string | null;
  attachments: TIssueAttachment[];
  fetchHtmlPreview: (attachmentId: string, signal?: AbortSignal) => Promise<string>;
  isOpen: boolean;
  onActiveAttachmentIdChange: (attachmentId: string) => void;
  onClose: () => void;
};

const stopPreviewEventPropagation = (event: SyntheticEvent) => {
  event.stopPropagation();
};

const isCanceledRequest = (error: unknown): boolean => {
  if (error instanceof DOMException && error.name === "AbortError") return true;
  if (!error || typeof error !== "object") return false;
  if ("code" in error && error.code === "ERR_CANCELED") return true;
  return "name" in error && error.name === "CanceledError";
};

export function IssueAttachmentMediaPreviewModal(props: TIssueAttachmentMediaPreviewModal) {
  const { activeAttachmentId, attachments, fetchHtmlPreview, isOpen, onActiveAttachmentIdChange, onClose } = props;
  const { t } = useTranslation();
  const htmlPreviewCacheRef = useRef<Record<string, THtmlPreviewState>>({});
  const [htmlPreviewCache, setHtmlPreviewCache] = useState<Record<string, THtmlPreviewState>>({});
  const [htmlPreviewRetry, setHtmlPreviewRetry] = useState(0);

  const activeIndex = useMemo(
    () => attachments.findIndex((attachment) => attachment.id === activeAttachmentId),
    [activeAttachmentId, attachments]
  );
  const activeAttachment = activeIndex >= 0 ? attachments[activeIndex] : undefined;
  const activePreviewType = activeAttachment ? getAttachmentPreviewType(activeAttachment) : undefined;
  const canNavigate = attachments.length > 1;
  const activeHtmlPreview = activeAttachment ? htmlPreviewCache[activeAttachment.id] : undefined;

  const updateHtmlPreviewCache = useCallback((attachmentId: string, previewState: THtmlPreviewState) => {
    htmlPreviewCacheRef.current[attachmentId] = previewState;
    setHtmlPreviewCache((currentCache) => ({ ...currentCache, [attachmentId]: previewState }));
  }, []);

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
        event.preventDefault();
        event.stopPropagation();
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

  useEffect(() => {
    if (!isOpen) {
      htmlPreviewCacheRef.current = {};
      setHtmlPreviewCache({});
      return;
    }
    if (!activeAttachment || activePreviewType !== "html") return;
    if (htmlPreviewCacheRef.current[activeAttachment.id]?.status === "success") return;

    const controller = new AbortController();
    updateHtmlPreviewCache(activeAttachment.id, { status: "loading" });
    void fetchHtmlPreview(activeAttachment.id, controller.signal)
      .then((content) => updateHtmlPreviewCache(activeAttachment.id, { status: "success", content }))
      .catch((error) =>
        isCanceledRequest(error)
          ? undefined
          : updateHtmlPreviewCache(activeAttachment.id, {
              status: "error",
            })
      );

    return () => controller.abort();
  }, [activeAttachment, activePreviewType, fetchHtmlPreview, htmlPreviewRetry, isOpen, updateHtmlPreviewCache]);

  if (!activeAttachment || !activePreviewType) return null;

  const fileName = getAttachmentDisplayName(activeAttachment);
  const previewURL = activePreviewType === "html" ? undefined : getAttachmentURL(activeAttachment, "inline");
  const downloadURL = getAttachmentURL(activeAttachment, "attachment");

  const handleDownload = () => {
    if (!downloadURL) return;
    window.open(downloadURL, "_blank", "noopener,noreferrer");
  };

  const handleRetryHtmlPreview = () => {
    delete htmlPreviewCacheRef.current[activeAttachment.id];
    setHtmlPreviewCache((currentCache) => {
      const nextCache = { ...currentCache };
      delete nextCache[activeAttachment.id];
      return nextCache;
    });
    setHtmlPreviewRetry((currentRetry) => currentRetry + 1);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Panel
        data-issue-attachment-media-preview
        data-prevent-outside-click
        width={EDialogWidth.VIIXL}
        className="flex h-[min(86vh,760px)] max-h-[86vh] w-[min(94vw,1120px)] max-w-none flex-col overflow-hidden"
        onClick={stopPreviewEventPropagation}
        onMouseDown={stopPreviewEventPropagation}
        onPointerDown={stopPreviewEventPropagation}
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

          {activePreviewType === "html" ? (
            <div className="flex h-full w-full flex-col overflow-hidden rounded-md border border-subtle bg-surface-1">
              <div className="flex flex-shrink-0 items-center gap-2 border-b border-subtle bg-warning-subtle px-3 py-2 text-12 text-warning-primary">
                <AlertTriangle className="size-4 flex-shrink-0" />
                <span>{t("attachment.html_preview.static_notice")}</span>
              </div>
              <div className="flex min-h-0 flex-1 items-center justify-center">
                {!activeHtmlPreview || activeHtmlPreview.status === "loading" ? (
                  <div className="flex items-center gap-2 text-13 text-secondary">
                    <LoaderCircle className="size-5 animate-spin" />
                    <span>{t("attachment.html_preview.loading")}</span>
                  </div>
                ) : activeHtmlPreview.status === "error" ? (
                  <div className="flex flex-col items-center gap-3 px-6 text-center">
                    <p className="text-13 text-secondary">{t("attachment.html_preview.error")}</p>
                    <Button variant="secondary" onClick={handleRetryHtmlPreview}>
                      {t("attachment.html_preview.retry")}
                    </Button>
                  </div>
                ) : (
                  <iframe
                    title={fileName}
                    className="pointer-events-none h-full w-full border-0 bg-white"
                    referrerPolicy="no-referrer"
                    sandbox=""
                    srcDoc={buildSandboxedHtmlPreviewDocument(activeHtmlPreview.content)}
                  />
                )}
              </div>
            </div>
          ) : (
            previewURL &&
            (activePreviewType === "image" ? (
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
            ))
          )}

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

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import type { FileRejection } from "react-dropzone";
import { useDropzone } from "react-dropzone";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
// hooks
import { useFileSize } from "@/hooks/use-file-size";
// types
import type { TAttachmentOperations } from "../issue-detail-widgets/attachments/helper";
// local imports
import { ATTACHMENT_BATCH_SIZE_LIMIT, isAttachmentBatchTooLarge } from "./batch-upload";

type TUseAttachmentBatchUpload = {
  attachmentOperations: Pick<TAttachmentOperations, "createMany">;
  disabled?: boolean;
  onUploadSettled?: () => void | Promise<void>;
};

const getFailedFilesMessage = (failedFiles: File[], t: (key: string, values?: Record<string, unknown>) => string) => {
  const visibleNames = failedFiles.slice(0, 3).map(({ name }) => name);
  const remainingCount = failedFiles.length - visibleNames.length;
  const names = visibleNames.join(", ");
  return remainingCount > 0
    ? t("attachment.batch.failed_files_with_more", { names, count: remainingCount })
    : t("attachment.batch.failed_files", { names });
};

export const useAttachmentBatchUpload = (props: TUseAttachmentBatchUpload) => {
  const { attachmentOperations, disabled = false, onUploadSettled } = props;
  const { t } = useTranslation();
  const { maxFileSize } = useFileSize();
  const [isUploading, setIsUploading] = useState(false);
  const [uploadingFileCount, setUploadingFileCount] = useState(0);

  const showUploadSummary = useCallback(
    (successfulCount: number, failedFiles: File[]) => {
      if (failedFiles.length === 0) {
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: t("attachment.batch.upload_success_title"),
          message: t("attachment.batch.upload_success", { count: successfulCount }),
        });
        return;
      }

      const message = getFailedFilesMessage(failedFiles, t);
      if (successfulCount === 0) {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("attachment.batch.upload_failed_title"),
          message,
        });
        return;
      }

      setToast({
        type: TOAST_TYPE.WARNING,
        title: t("attachment.batch.upload_partial_title"),
        message: `${t("attachment.batch.upload_partial", {
          successCount: successfulCount,
          failedCount: failedFiles.length,
        })} ${message}`,
      });
    },
    [t]
  );

  const onDrop = useCallback(
    async (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      const totalFileCount = acceptedFiles.length + rejectedFiles.length;
      const rejectedForBatchSize = rejectedFiles.some(({ errors }) =>
        errors.some(({ code }) => code === "too-many-files")
      );
      if (isAttachmentBatchTooLarge(totalFileCount) || rejectedForBatchSize) {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("attachment.batch.too_many_files_title"),
          message: t("attachment.batch.too_many_files", { count: ATTACHMENT_BATCH_SIZE_LIMIT }),
        });
        return;
      }
      if (totalFileCount === 0) return;

      const rejectedFileList = rejectedFiles.map(({ file }) => file);
      if (acceptedFiles.length === 0) {
        showUploadSummary(0, rejectedFileList);
        return;
      }

      setIsUploading(true);
      setUploadingFileCount(acceptedFiles.length);
      try {
        const result = await attachmentOperations.createMany(acceptedFiles);
        try {
          await onUploadSettled?.();
        } catch (error) {
          console.error("Failed to refresh attachment activity after upload:", error);
        }
        showUploadSummary(result.successful.length, rejectedFileList.concat(result.failed.map(({ file }) => file)));
      } catch (_error) {
        showUploadSummary(0, rejectedFileList.concat(acceptedFiles));
      } finally {
        setIsUploading(false);
        setUploadingFileCount(0);
      }
    },
    [attachmentOperations, onUploadSettled, showUploadSummary, t]
  );

  const dropzone = useDropzone({
    onDrop,
    maxFiles: ATTACHMENT_BATCH_SIZE_LIMIT,
    maxSize: maxFileSize,
    multiple: true,
    disabled: isUploading || disabled,
  });

  return {
    ...dropzone,
    isUploading,
    uploadingFileCount,
  };
};

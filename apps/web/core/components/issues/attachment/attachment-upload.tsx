/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
// types
import type { TAttachmentOperations } from "../issue-detail-widgets/attachments/helper";
// local imports
import { useAttachmentBatchUpload } from "./use-attachment-batch-upload";

type TAttachmentOperationsModal = Pick<TAttachmentOperations, "createMany">;

type Props = {
  workspaceSlug: string;
  disabled?: boolean;
  attachmentOperations: TAttachmentOperationsModal;
};

export const IssueAttachmentUpload = observer(function IssueAttachmentUpload(props: Props) {
  const { disabled = false, attachmentOperations } = props;
  const { t } = useTranslation();
  const { getRootProps, getInputProps, isDragActive, isDragReject, isUploading, uploadingFileCount } =
    useAttachmentBatchUpload({
      attachmentOperations,
      disabled,
    });

  return (
    <div
      {...getRootProps()}
      className={`flex h-[60px] items-center justify-center rounded-md border-2 border-dashed bg-accent-primary/5 px-4 text-11 text-accent-primary ${
        isDragActive ? "border-accent-strong bg-accent-primary/10" : "border-subtle"
      } ${isDragReject ? "bg-danger-subtle" : ""} ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}
    >
      <input {...getInputProps()} />
      <span className="flex items-center gap-2">
        {isDragActive ? (
          <p>{t("attachment.batch.drop_files")}</p>
        ) : isUploading ? (
          <p className="text-center">{t("attachment.batch.uploading", { count: uploadingFileCount })}</p>
        ) : (
          <p className="text-center">{t("attachment.batch.select_files")}</p>
        )}
      </span>
    </div>
  );
});

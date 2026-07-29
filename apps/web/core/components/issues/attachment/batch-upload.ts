/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TAttachmentBatchUploadFailure = {
  file: File;
  error: unknown;
};

export type TAttachmentBatchUploadResult = {
  successful: File[];
  failed: TAttachmentBatchUploadFailure[];
};

export const ATTACHMENT_BATCH_SIZE_LIMIT = 20;
export const ATTACHMENT_UPLOAD_CONCURRENCY = 3;

export const isAttachmentBatchTooLarge = (fileCount: number): boolean => fileCount > ATTACHMENT_BATCH_SIZE_LIMIT;

export const uploadFilesWithConcurrency = async (
  files: File[],
  uploadFile: (file: File) => Promise<void>,
  concurrency: number = ATTACHMENT_UPLOAD_CONCURRENCY
): Promise<TAttachmentBatchUploadResult> => {
  const successful: File[] = [];
  const failed: TAttachmentBatchUploadFailure[] = [];
  let nextFileIndex = 0;

  const uploadNextFile = async () => {
    if (nextFileIndex >= files.length) return;

    const currentFile = files[nextFileIndex];
    nextFileIndex += 1;

    try {
      await uploadFile(currentFile);
      successful.push(currentFile);
    } catch (error) {
      failed.push({ file: currentFile, error });
    }

    await uploadNextFile();
  };

  const workerCount = Math.min(Math.max(1, concurrency), files.length);
  const workers = Array.from({ length: workerCount }, () => uploadNextFile());
  await Promise.allSettled(workers);

  return { successful, failed };
};

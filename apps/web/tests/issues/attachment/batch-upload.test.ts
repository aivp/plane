/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, test } from "vitest";
import {
  isAttachmentBatchTooLarge,
  uploadFilesWithConcurrency,
} from "../../../core/components/issues/attachment/batch-upload";

const file = (name: string): File => ({ name }) as File;

describe("uploadFilesWithConcurrency", () => {
  test("allows twenty files and rejects the twenty-first", () => {
    expect(isAttachmentBatchTooLarge(20)).toBe(false);
    expect(isAttachmentBatchTooLarge(21)).toBe(true);
  });

  test("keeps uploading after failures without exceeding the concurrency limit", async () => {
    const files = ["one", "two", "three", "four", "five", "six"].map(file);
    let activeUploads = 0;
    let maxActiveUploads = 0;

    const result = await uploadFilesWithConcurrency(
      files,
      async (currentFile) => {
        activeUploads += 1;
        maxActiveUploads = Math.max(maxActiveUploads, activeUploads);
        await new Promise((resolve) => setTimeout(resolve, 5));
        activeUploads -= 1;
        if (currentFile.name === "two" || currentFile.name === "five") {
          throw new Error(`Failed ${currentFile.name}`);
        }
      },
      3
    );

    expect(maxActiveUploads).toBe(3);
    expect(new Set(result.successful.map(({ name }) => name))).toEqual(new Set(["four", "one", "six", "three"]));
    expect(new Set(result.failed.map(({ file: failedFile }) => failedFile.name))).toEqual(new Set(["five", "two"]));
  });
});

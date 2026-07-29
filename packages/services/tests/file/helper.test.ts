/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, test } from "vitest";
import { getFileMetaDataForUpload } from "../../src/file/helper";

describe("HTML attachment MIME detection", () => {
  test.each(["report.html", "report.htm"])("uses text/html for %s when the browser MIME is empty", async (name) => {
    const file = new File(["<!doctype html><h1>Report</h1>"], name);

    await expect(getFileMetaDataForUpload(file)).resolves.toMatchObject({
      name,
      type: "text/html",
    });
  });
});

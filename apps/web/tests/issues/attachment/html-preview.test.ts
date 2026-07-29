/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, test } from "vitest";
import type { TIssueAttachment } from "@plane/types";
import { getAttachmentPreviewType } from "../../../core/components/issues/attachment/helpers";
import { buildSandboxedHtmlPreviewDocument } from "../../../core/components/issues/attachment/html-preview";

const attachment = (name: string, type?: string): TIssueAttachment =>
  ({
    attributes: { name, size: 100, type },
  }) as TIssueAttachment;

describe("HTML attachment preview", () => {
  test("recognizes HTML by MIME type and legacy file extension", () => {
    expect(getAttachmentPreviewType(attachment("report.bin", "text/html"))).toBe("html");
    expect(getAttachmentPreviewType(attachment("report.htm"))).toBe("html");
    expect(getAttachmentPreviewType(attachment("photo.png", "image/png"))).toBe("image");
  });

  test("wraps sanitized HTML in a network-blocking content security policy", () => {
    const document = buildSandboxedHtmlPreviewDocument("<h1>Quarterly report</h1>");

    expect(document).toContain("default-src 'none'");
    expect(document).toContain("connect-src 'none'");
    expect(document).toContain("form-action 'none'");
    expect(document).toContain("base-uri 'none'");
    expect(document).toContain("img-src data:");
    expect(document).toContain("font-src data:");
    expect(document).not.toContain("media-src data:");
    expect(document).toContain("<h1>Quarterly report</h1>");
  });
});

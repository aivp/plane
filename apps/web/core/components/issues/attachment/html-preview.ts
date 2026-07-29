/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const HTML_PREVIEW_CONTENT_SECURITY_POLICY = [
  "default-src 'none'",
  "connect-src 'none'",
  "frame-src 'none'",
  "object-src 'none'",
  "form-action 'none'",
  "base-uri 'none'",
  "style-src 'unsafe-inline'",
  "img-src data:",
  "font-src data:",
].join("; ");

export const buildSandboxedHtmlPreviewDocument = (sanitizedHtml: string): string => `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="${HTML_PREVIEW_CONTENT_SECURITY_POLICY}">
    <meta name="referrer" content="no-referrer">
    <style>
      html, body { min-height: 100%; margin: 0; padding: 0; }
      a, button, input, select, textarea, form { pointer-events: none !important; }
    </style>
  </head>
  <body>${sanitizedHtml}</body>
</html>`;

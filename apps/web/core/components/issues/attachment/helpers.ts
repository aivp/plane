/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TIssueAttachment } from "@plane/types";
import { getFileURL } from "@plane/utils";

export type TAttachmentMediaType = "image" | "video";
export type TAttachmentPreviewType = TAttachmentMediaType | "html";
export type TAttachmentDisposition = "inline" | "attachment";

const IMAGE_EXTENSIONS = new Set(["avif", "bmp", "gif", "jpeg", "jpg", "png", "svg", "tif", "tiff", "webp"]);
const VIDEO_EXTENSIONS = new Set(["avi", "m4v", "mov", "mp4", "mpeg", "mpg", "ogg", "ogv", "webm", "wmv"]);

export const getAttachmentDisplayName = (attachment: TIssueAttachment): string =>
  attachment.attributes.name || "Untitled attachment";

export const getAttachmentExtension = (attachment: TIssueAttachment): string => {
  const fileName = attachment.attributes.name;
  const dotIndex = fileName.lastIndexOf(".");
  if (dotIndex < 0 || dotIndex === fileName.length - 1) return "";
  return fileName.slice(dotIndex + 1).toLowerCase();
};

export const getAttachmentMediaType = (attachment: TIssueAttachment): TAttachmentMediaType | undefined => {
  const mimeType = attachment.attributes.type?.toLowerCase();
  if (mimeType?.startsWith("image/")) return "image";
  if (mimeType?.startsWith("video/")) return "video";

  const extension = getAttachmentExtension(attachment);
  if (IMAGE_EXTENSIONS.has(extension)) return "image";
  if (VIDEO_EXTENSIONS.has(extension)) return "video";

  return undefined;
};

export const getAttachmentPreviewType = (attachment: TIssueAttachment): TAttachmentPreviewType | undefined => {
  const mimeType = attachment.attributes.type?.split(";")[0]?.trim().toLowerCase();
  const extension = getAttachmentExtension(attachment);
  if (mimeType === "text/html" || extension === "html" || extension === "htm") return "html";

  return getAttachmentMediaType(attachment);
};

export const isAttachmentMediaPreviewable = (attachment: TIssueAttachment): boolean =>
  !!getAttachmentMediaType(attachment);

export const isAttachmentPreviewable = (attachment: TIssueAttachment): boolean =>
  !!getAttachmentPreviewType(attachment);

export const getAttachmentURL = (
  attachment: TIssueAttachment,
  disposition: TAttachmentDisposition
): string | undefined => {
  const fileURL = getFileURL(attachment.asset_url ?? "");
  if (!fileURL) return undefined;

  const separator = fileURL.includes("?") ? "&" : "?";
  return `${fileURL}${separator}disposition=${disposition}`;
};

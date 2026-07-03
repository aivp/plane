/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useTranslation } from "@plane/i18n";
import { ChevronDownIcon, ChevronUpIcon } from "@plane/propel/icons";

const FILTER_HEADER_TRANSLATION_KEYS: Record<string, string> = {
  Access: "common.access_label",
  Assignee: "common.assignee",
  "Created by": "common.created_by",
  "Created date": "common.created_date",
  Cycle: "common.cycle",
  "Due date": "common.due_date",
  Label: "common.label",
  Lead: "lead",
  Members: "common.members",
  Mention: "common.mention",
  Module: "common.module",
  Priority: "common.priority",
  Project: "common.project",
  State: "common.state",
  Status: "common.status",
  "Status of the cycle": "common.cycle_status",
  "State group": "common.state_group",
  "Start date": "common.start_date",
  "Sub-group by": "common.sub_group_by",
};

type Props = {
  title: string;
  isPreviewEnabled: boolean;
  handleIsPreviewEnabled: () => void;
};

export function FilterHeader({ title, isPreviewEnabled, handleIsPreviewEnabled }: Props) {
  const { t } = useTranslation();
  const titleParts = title.match(/^(.*?)(\s*\(\d+\))?$/);
  const baseTitle = titleParts?.[1]?.trim() ?? title;
  const countSuffix = titleParts?.[2] ?? "";
  const translatedTitle = FILTER_HEADER_TRANSLATION_KEYS[baseTitle]
    ? `${t(FILTER_HEADER_TRANSLATION_KEYS[baseTitle])}${countSuffix}`
    : title;

  return (
    <div className="sticky top-0 flex items-center justify-between gap-2 bg-surface-1">
      <div className="flex-grow truncate text-caption-sm-medium text-placeholder">{translatedTitle}</div>
      <button
        type="button"
        className="grid h-5 w-5 flex-shrink-0 place-items-center rounded-sm hover:bg-layer-transparent-hover"
        onClick={handleIsPreviewEnabled}
      >
        {isPreviewEnabled ? <ChevronUpIcon height={14} width={14} /> : <ChevronDownIcon height={14} width={14} />}
      </button>
    </div>
  );
}

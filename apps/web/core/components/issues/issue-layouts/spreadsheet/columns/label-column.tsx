/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
// types
import { LabelPropertyIcon } from "@plane/propel/icons";
import { Tooltip } from "@plane/propel/tooltip";
import type { IIssueLabel, TIssue } from "@plane/types";
import { cn } from "@plane/utils";
// hooks
import { useLabel } from "@/hooks/store/use-label";
import { usePlatformOS } from "@/hooks/use-platform-os";
// components
import { LabelDropdown } from "../../properties";

type Props = {
  issue: TIssue;
  onClose: () => void;
  onChange: (issue: TIssue, data: Partial<TIssue>, updates: any) => void;
  disabled: boolean;
};

const MAX_VISIBLE_LABELS = 3;

const isIssueLabel = (label: IIssueLabel | undefined): label is IIssueLabel => !!label;

type LabelPreviewProps = {
  labelIds: string[];
  labels: IIssueLabel[];
  disabled: boolean;
};

function SpreadsheetLabelPreview({ labelIds, labels, disabled }: LabelPreviewProps) {
  const { isMobile } = usePlatformOS();

  const visibleLabels = labels.slice(0, MAX_VISIBLE_LABELS);
  const hiddenLabelsCount = Math.max(labelIds.length - visibleLabels.length, 0);
  const tooltipContent =
    labels.length > 0
      ? labels.map((label) => label.name).join(", ")
      : labelIds.length > 0
        ? `${labelIds.length} Labels`
        : "None";

  return (
    <Tooltip position="top" tooltipHeading="Labels" tooltipContent={tooltipContent} isMobile={isMobile}>
      <div
        className={cn(
          "flex h-full w-full min-w-0 items-center overflow-hidden px-page-x py-2 text-caption-sm-regular",
          disabled ? "cursor-not-allowed" : "cursor-pointer"
        )}
      >
        {labelIds.length > 0 ? (
          <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden">
            {visibleLabels.length > 0 ? (
              visibleLabels.map((label) => (
                <div
                  key={label.id}
                  className="flex h-6 max-w-24 min-w-0 flex-1 items-center gap-1 rounded-sm border border-strong bg-surface-1 px-1.5 text-secondary"
                >
                  <span
                    className="h-2 w-2 flex-shrink-0 rounded-full"
                    style={{
                      backgroundColor: label.color ?? "#000000",
                    }}
                  />
                  <span className="min-w-0 truncate">{label.name}</span>
                </div>
              ))
            ) : (
              <div className="flex h-6 min-w-0 items-center gap-1.5 rounded-sm border border-strong bg-surface-1 px-2 text-secondary">
                <span className="h-2 w-2 flex-shrink-0 rounded-full bg-accent-primary" />
                <span className="truncate">{`${labelIds.length} Labels`}</span>
              </div>
            )}
            {hiddenLabelsCount > 0 && (
              <div className="flex h-6 flex-shrink-0 items-center rounded-sm border border-strong bg-surface-1 px-2 text-secondary">
                +{hiddenLabelsCount}
              </div>
            )}
          </div>
        ) : (
          <div className="flex min-w-0 items-center gap-2 text-placeholder">
            <LabelPropertyIcon className="h-3.5 w-3.5 flex-shrink-0" />
            <span className="truncate">Select labels</span>
          </div>
        )}
      </div>
    </Tooltip>
  );
}

export const SpreadsheetLabelColumn = observer(function SpreadsheetLabelColumn(props: Props) {
  const { issue, onChange, disabled, onClose } = props;
  // hooks
  const { labelMap } = useLabel();

  const labelIds = issue?.label_ids || [];
  const selectedLabels = labelIds.map((id) => labelMap[id]).filter(isIssueLabel);

  return (
    <div className="h-11 w-full border-b-[0.5px] border-subtle">
      <LabelDropdown
        projectId={issue.project_id ?? null}
        value={labelIds}
        defaultOptions={selectedLabels}
        onChange={(data) => onChange(issue, { label_ids: data }, { changed_property: "labels", change_details: data })}
        className="h-full w-full"
        buttonClassName="w-full h-full group-[.selected-issue-row]:bg-accent-primary/5 group-[.selected-issue-row]:hover:bg-accent-primary/10 rounded-none"
        hideDropdownArrow
        disabled={disabled}
        onClose={onClose}
        fullWidth
        fullHeight
        label={<SpreadsheetLabelPreview labelIds={labelIds} labels={selectedLabels} disabled={disabled} />}
      />
    </div>
  );
});

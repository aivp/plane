/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { CalendarDays } from "lucide-react";
// ui
import { useTranslation } from "@plane/i18n";
import { CalendarAfterIcon, CalendarBeforeIcon } from "@plane/propel/icons";
import { CustomSelect } from "@plane/ui";

type Props = {
  title: string;
  value: string;
  onChange: (value: string) => void;
};

type DueDate = {
  i18nKey: string;
  value: string;
  icon: any;
};

const dueDateRange: DueDate[] = [
  {
    i18nKey: "date_filters.before",
    value: "before",
    icon: <CalendarBeforeIcon className="h-4 w-4" />,
  },
  {
    i18nKey: "date_filters.after",
    value: "after",
    icon: <CalendarAfterIcon className="h-4 w-4" />,
  },
  {
    i18nKey: "date_filters.range",
    value: "range",
    icon: <CalendarDays className="h-4 w-4" />,
  },
];

export function DateFilterSelect({ title, value, onChange }: Props) {
  const { t } = useTranslation();
  const selectedOption = dueDateRange.find((item) => item.value === value);

  return (
    <CustomSelect
      value={value}
      label={
        <div className="flex items-center gap-2 text-11">
          {selectedOption?.icon}
          <span>
            {title} {selectedOption ? t(selectedOption.i18nKey) : ""}
          </span>
        </div>
      }
      onChange={onChange}
    >
      {dueDateRange.map((option, index) => (
        <CustomSelect.Option key={index} value={option.value}>
          <div className="flex items-center gap-2">
            <span>{option.icon}</span>
            {title} {t(option.i18nKey)}
          </div>
        </CustomSelect.Option>
      ))}
    </CustomSelect>
  );
}

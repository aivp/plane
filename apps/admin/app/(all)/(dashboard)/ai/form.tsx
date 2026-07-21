/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Controller, useForm } from "react-hook-form";
import { Lightbulb } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CustomSelect } from "@plane/ui";
import type { IFormattedInstanceConfiguration, TInstanceAIConfigurationKeys } from "@plane/types";
// components
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
// hooks
import { useInstance } from "@/hooks/store";

type IInstanceAIForm = {
  config: IFormattedInstanceConfiguration;
};

type AIFormValues = Record<TInstanceAIConfigurationKeys, string>;

const AI_PROVIDER_OPTIONS: Record<string, string> = {
  openai: "OpenAI-compatible",
  anthropic: "Anthropic",
};

export function InstanceAIForm(props: IInstanceAIForm) {
  const { config } = props;
  // store
  const { updateInstanceConfigurations } = useInstance();
  // form data
  const {
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<AIFormValues>({
    defaultValues: {
      LLM_PROVIDER: config["LLM_PROVIDER"] || "openai",
      LLM_API_KEY: config["LLM_API_KEY"] || "",
      LLM_MODEL: config["LLM_MODEL"] || "gpt-4o-mini",
      LLM_BASE_URL: config["LLM_BASE_URL"] || "",
    },
  });

  const aiFormFields: TControllerInputFormField[] = [
    {
      key: "LLM_MODEL",
      type: "text",
      label: "LLM Model",
      description: (
        <>
          Enter the model identifier for your selected provider.{" "}
          <a
            href="https://docs.anthropic.com/en/docs/about-claude/models/overview"
            target="_blank"
            className="text-accent-primary hover:underline"
            rel="noreferrer"
            aria-label="Anthropic models documentation"
          >
            Anthropic models
          </a>
        </>
      ),
      placeholder: "gpt-4o-mini or claude-3-5-sonnet-20241022",
      error: Boolean(errors.LLM_MODEL),
      required: false,
    },
    {
      key: "LLM_BASE_URL",
      type: "text",
      label: "Base URL",
      description:
        "Optional. OpenAI-compatible endpoints usually include /v1; Anthropic proxies should follow their service URL.",
      placeholder: "https://api.openai.com/v1",
      error: Boolean(errors.LLM_BASE_URL),
      required: false,
    },
    {
      key: "LLM_API_KEY",
      type: "password",
      label: "API key",
      description: "Use the API key for the selected provider or gateway.",
      placeholder: "sk-...",
      error: Boolean(errors.LLM_API_KEY),
      required: false,
    },
  ];

  const onSubmit = async (formData: AIFormValues) => {
    const payload: Partial<AIFormValues> = { ...formData };

    await updateInstanceConfigurations(payload)
      .then(() =>
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "Success",
          message: "AI Settings updated successfully",
        })
      )
      .catch((err) => console.error(err));
  };

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <div>
          <div className="pb-1 text-18 font-medium text-primary">AI provider</div>
          <div className="text-13 font-regular text-tertiary">
            Configure an OpenAI-compatible endpoint or Anthropic for Plane AI features.
          </div>
        </div>
        <div className="grid-col grid w-full grid-cols-1 items-center justify-between gap-x-12 gap-y-8 lg:grid-cols-3">
          <div className="flex flex-col gap-1">
            <h4 className="text-13 text-tertiary">Provider</h4>
            <Controller
              control={control}
              name="LLM_PROVIDER"
              render={({ field: { value, onChange } }) => (
                <CustomSelect
                  value={value || "openai"}
                  label={AI_PROVIDER_OPTIONS[value] || AI_PROVIDER_OPTIONS.openai}
                  onChange={onChange}
                  buttonClassName="rounded-md border-subtle"
                  input
                >
                  {Object.entries(AI_PROVIDER_OPTIONS).map(([key, label]) => (
                    <CustomSelect.Option key={key} value={key} className="w-full">
                      {label}
                    </CustomSelect.Option>
                  ))}
                </CustomSelect>
              )}
            />
            <p className="pt-0.5 text-11 text-tertiary">Choose the provider used by the existing Plane AI endpoints.</p>
          </div>
          {aiFormFields.map((field) => (
            <ControllerInput
              key={field.key}
              control={control}
              type={field.type}
              name={field.key}
              label={field.label}
              description={field.description}
              placeholder={field.placeholder}
              error={field.error}
              required={field.required}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-col items-start gap-4">
        <Button variant="primary" size="lg" onClick={handleSubmit(onSubmit)} loading={isSubmitting}>
          {isSubmitting ? "Saving" : "Save changes"}
        </Button>

        <div className="relative inline-flex items-center gap-1.5 rounded-sm border border-accent-subtle bg-accent-subtle px-4 py-2 text-caption-sm-regular text-accent-secondary">
          <Lightbulb className="size-4" />
          <div>
            If you have a preferred AI models vendor, please get in{" "}
            <a className="font-medium underline" href="https://plane.so/contact">
              touch with us.
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

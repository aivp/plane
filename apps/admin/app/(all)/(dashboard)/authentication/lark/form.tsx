/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { isEmpty } from "lodash-es";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { Monitor, PanelTop } from "lucide-react";
import { API_BASE_URL } from "@plane/constants";
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { InstanceService } from "@plane/services";
import type {
  IFormattedInstanceConfiguration,
  TLarkInstanceStatus,
  TInstanceLarkAuthenticationConfigurationKeys,
} from "@plane/types";
import { CodeBlock } from "@/components/common/code-block";
import { ConfirmDiscardModal } from "@/components/common/confirm-discard-modal";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
import type { TControllerSwitchFormField } from "@/components/common/controller-switch";
import { ControllerSwitch } from "@/components/common/controller-switch";
import type { TCopyField } from "@/components/common/copy-field";
import { CopyField } from "@/components/common/copy-field";
import { useInstance } from "@/hooks/store";

type Props = {
  config: IFormattedInstanceConfiguration;
};

type LarkConfigFormValues = Record<TInstanceLarkAuthenticationConfigurationKeys, string>;

const instanceService = new InstanceService();

const configValue = (response: { key: string; value: string }[], key: TInstanceLarkAuthenticationConfigurationKeys) =>
  response.find((item) => item.key === key)?.value;

export function InstanceLarkConfigForm(props: Props) {
  const { config } = props;
  const [isDiscardChangesModalOpen, setIsDiscardChangesModalOpen] = useState(false);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [larkStatus, setLarkStatus] = useState<TLarkInstanceStatus | null>(null);
  const { updateInstanceConfigurations } = useInstance();
  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<LarkConfigFormValues>({
    defaultValues: {
      LARK_CLIENT_ID: config["LARK_CLIENT_ID"],
      LARK_CLIENT_SECRET: config["LARK_CLIENT_SECRET"],
      LARK_BASE_DOMAIN: config["LARK_BASE_DOMAIN"] || "feishu.cn",
      LARK_DEFAULT_WORKSPACE_SLUG: config["LARK_DEFAULT_WORKSPACE_SLUG"] || "",
      LARK_DEFAULT_WORKSPACE_ROLE: config["LARK_DEFAULT_WORKSPACE_ROLE"] || "15",
      LARK_AUTO_SYNC_ENABLED: config["LARK_AUTO_SYNC_ENABLED"] || "0",
      LARK_OFFBOARDING_POLICY: config["LARK_OFFBOARDING_POLICY"] || "deactivate_workspace_member",
      LARK_NOTIFICATIONS_ENABLED: config["LARK_NOTIFICATIONS_ENABLED"] || "0",
      LARK_CONNECTOR_ENABLED: config["LARK_CONNECTOR_ENABLED"] || "0",
      PLANE_PUBLIC_BASE_URL: config["PLANE_PUBLIC_BASE_URL"] || "",
    },
  });

  const originURL = !isEmpty(API_BASE_URL) ? API_BASE_URL : typeof window !== "undefined" ? window.location.origin : "";

  const fetchLarkStatus = () =>
    instanceService
      .larkStatus()
      .then(setLarkStatus)
      .catch(() => setLarkStatus(null));

  useEffect(() => {
    void fetchLarkStatus();
  }, []);

  const LARK_FORM_FIELDS: TControllerInputFormField[] = [
    {
      key: "LARK_CLIENT_ID",
      type: "text",
      label: "App ID",
      description: <>Use the App ID from the Feishu developer console.</>,
      placeholder: "cli_a73f9f2d4e70100b",
      error: Boolean(errors.LARK_CLIENT_ID),
      required: true,
    },
    {
      key: "LARK_CLIENT_SECRET",
      type: "password",
      label: "App secret",
      description: <>Use the App Secret from the Feishu developer console.</>,
      placeholder: "Feishu app secret",
      error: Boolean(errors.LARK_CLIENT_SECRET),
      required: true,
    },
    {
      key: "LARK_DEFAULT_WORKSPACE_SLUG",
      type: "text",
      label: "Default workspace slug",
      description: <>Contact events sync into this workspace when auto sync is enabled.</>,
      placeholder: "engineering",
      error: Boolean(errors.LARK_DEFAULT_WORKSPACE_SLUG),
      required: false,
    },
    {
      key: "LARK_DEFAULT_WORKSPACE_ROLE",
      type: "text",
      label: "Default role",
      description: <>Use 15 for Member, 5 for Guest, or 20 for Admin.</>,
      placeholder: "15",
      error: Boolean(errors.LARK_DEFAULT_WORKSPACE_ROLE),
      required: true,
    },
    {
      key: "PLANE_PUBLIC_BASE_URL",
      type: "text",
      label: "Plane public URL",
      description: <>Used to build Feishu notification links.</>,
      placeholder: "https://plane.example.com",
      error: Boolean(errors.PLANE_PUBLIC_BASE_URL),
      required: false,
    },
  ];

  const LARK_SWITCH_FIELDS: TControllerSwitchFormField<LarkConfigFormValues>[] = [
    {
      name: "LARK_AUTO_SYNC_ENABLED",
      label: "Auto sync contacts",
    },
    {
      name: "LARK_NOTIFICATIONS_ENABLED",
      label: "Feishu notifications",
    },
    {
      name: "LARK_CONNECTOR_ENABLED",
      label: "Long connection connector",
    },
  ];

  const LARK_SERVICE_FIELDS: TCopyField[] = [
    {
      key: "App_Callback_URI",
      label: "App callback URI",
      url: `${originURL}/auth/lark/callback/`,
      description: (
        <p>
          Paste this into the Feishu OAuth <CodeBlock darkerShade>Redirect URL</CodeBlock> list.
        </p>
      ),
    },
    {
      key: "Space_Callback_URI",
      label: "Space callback URI",
      url: `${originURL}/auth/spaces/lark/callback/`,
      description: (
        <p>
          Paste this into the same Feishu OAuth <CodeBlock darkerShade>Redirect URL</CodeBlock> list.
        </p>
      ),
    },
  ];

  const onSubmit = async (formData: LarkConfigFormValues) => {
    const payload: Partial<LarkConfigFormValues> = {
      ...formData,
      LARK_BASE_DOMAIN: "feishu.cn",
    };

    try {
      const response = await updateInstanceConfigurations(payload);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Done!",
        message: "Your Feishu authentication is configured.",
      });
      reset({
        LARK_CLIENT_ID: configValue(response, "LARK_CLIENT_ID"),
        LARK_CLIENT_SECRET: configValue(response, "LARK_CLIENT_SECRET"),
        LARK_BASE_DOMAIN: configValue(response, "LARK_BASE_DOMAIN") || "feishu.cn",
        LARK_DEFAULT_WORKSPACE_SLUG: configValue(response, "LARK_DEFAULT_WORKSPACE_SLUG"),
        LARK_DEFAULT_WORKSPACE_ROLE: configValue(response, "LARK_DEFAULT_WORKSPACE_ROLE") || "15",
        LARK_AUTO_SYNC_ENABLED: configValue(response, "LARK_AUTO_SYNC_ENABLED") || "0",
        LARK_OFFBOARDING_POLICY: configValue(response, "LARK_OFFBOARDING_POLICY") || "deactivate_workspace_member",
        LARK_NOTIFICATIONS_ENABLED: configValue(response, "LARK_NOTIFICATIONS_ENABLED") || "0",
        LARK_CONNECTOR_ENABLED: configValue(response, "LARK_CONNECTOR_ENABLED") || "0",
        PLANE_PUBLIC_BASE_URL: configValue(response, "PLANE_PUBLIC_BASE_URL") || "",
      });
    } catch (err) {
      console.error(err);
    }
  };

  const testConnection = async () => {
    setIsTestingConnection(true);
    try {
      await instanceService.testLarkConnection();
      void fetchLarkStatus();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Connected",
        message: "Plane can reach Feishu with the configured app credentials.",
      });
    } catch (err) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Connection failed",
        message: "Check the Feishu app credentials and contact permissions.",
      });
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleGoBack = (e: React.MouseEvent<HTMLAnchorElement, MouseEvent>) => {
    if (isDirty) {
      e.preventDefault();
      setIsDiscardChangesModalOpen(true);
    }
  };

  return (
    <>
      <ConfirmDiscardModal
        isOpen={isDiscardChangesModalOpen}
        onDiscardHref="/authentication"
        handleClose={() => setIsDiscardChangesModalOpen(false)}
      />
      <div className="grid w-full grid-cols-2 gap-x-12 gap-y-8">
        <div className="col-span-2 flex flex-col gap-y-4 pt-1 md:col-span-1">
          <div className="pt-2.5 text-18 font-medium">Feishu-provided details for Plane</div>
          {LARK_FORM_FIELDS.map((field) => (
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
          {LARK_SWITCH_FIELDS.map((field) => (
            <ControllerSwitch key={field.name} control={control} field={field} />
          ))}
          <div className="flex flex-wrap items-center gap-4 pt-4">
            <Button
              variant="primary"
              size="lg"
              onClick={(e) => void handleSubmit(onSubmit)(e)}
              loading={isSubmitting}
              disabled={!isDirty}
            >
              {isSubmitting ? "Saving" : "Save changes"}
            </Button>
            <Button variant="secondary" size="lg" onClick={testConnection} loading={isTestingConnection}>
              Test connection
            </Button>
            <Link href="/authentication" className={getButtonStyling("secondary", "lg")} onClick={handleGoBack}>
              Go back
            </Link>
          </div>
        </div>
        <div className="col-span-2 flex flex-col gap-y-6 md:col-span-1">
          <div className="pt-2 text-18 font-medium">Plane-provided details for Feishu</div>
          <div className="flex flex-col overflow-hidden rounded-lg">
            <div className="flex items-center gap-x-3 bg-layer-3 px-6 py-3 text-11 font-medium text-secondary uppercase">
              <Monitor className="h-3 w-3" />
              Web
            </div>
            <div className="flex flex-col gap-y-4 bg-layer-1 px-6 py-4">
              <CopyField
                label="Allowed domain"
                url="feishu.cn"
                description={<p>Plane only supports the domestic Feishu tenant domain.</p>}
              />
              {LARK_SERVICE_FIELDS.map((field) => (
                <CopyField key={field.key} label={field.label} url={field.url} description={field.description} />
              ))}
            </div>
          </div>
          <div className="flex flex-col overflow-hidden rounded-lg">
            <div className="flex items-center gap-x-3 bg-layer-3 px-6 py-3 text-11 font-medium text-secondary uppercase">
              <PanelTop className="h-3 w-3" />
              Events
            </div>
            <div className="bg-layer-1 px-6 py-4 text-13 text-secondary">
              <div className="flex flex-col gap-1">
                <div>Use the Feishu app long connection mode and run the `lark-connector` service.</div>
                <div>
                  Connector:{" "}
                  <span className="font-medium text-primary">
                    {larkStatus?.connector.healthy ? "connected" : "disconnected"}
                  </span>
                </div>
                <div>
                  Default workspace:{" "}
                  <span className="font-medium text-primary">
                    {larkStatus?.default_workspace_slug || "not configured"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

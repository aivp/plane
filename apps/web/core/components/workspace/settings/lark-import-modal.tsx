/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { Button } from "@plane/propel/button";
import { SearchIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { WorkspaceLarkService } from "@plane/services";
import type { TLarkContact, TLarkSyncRun, TLarkWorkspaceRole } from "@plane/types";
import { Avatar, Checkbox, EModalPosition, EModalWidth, Loader, ModalCore } from "@plane/ui";
import useDebounce from "@/hooks/use-debounce";

type Props = {
  isOpen: boolean;
  workspaceSlug: string;
  onClose: () => void;
  onImported: () => void;
};

const workspaceLarkService = new WorkspaceLarkService();

const roleOptions: { label: string; value: TLarkWorkspaceRole }[] = [
  { label: "Member", value: 15 },
  { label: "Guest", value: 5 },
  { label: "Admin", value: 20 },
];

export function LarkImportModal(props: Props) {
  const { isOpen, workspaceSlug, onClose, onImported } = props;
  const [contacts, setContacts] = useState<TLarkContact[]>([]);
  const [syncRuns, setSyncRuns] = useState<TLarkSyncRun[]>([]);
  const [selectedOpenIds, setSelectedOpenIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<TLarkWorkspaceRole>(15);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const debouncedQuery = useDebounce(query, 400);

  const fetchContacts = () => {
    setIsLoading(true);
    workspaceLarkService
      .contacts(workspaceSlug, { search: debouncedQuery, limit: 500 })
      .then((response) => setContacts(response.contacts))
      .catch(() =>
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Error",
          message: "Failed to fetch Feishu contacts.",
        })
      )
      .finally(() => setIsLoading(false));
  };

  const fetchSyncRuns = () =>
    workspaceLarkService
      .syncRuns(workspaceSlug)
      .then((response) => setSyncRuns(response.sync_runs))
      .catch(() => undefined);

  useEffect(() => {
    if (!isOpen) return;
    fetchContacts();
  }, [debouncedQuery, isOpen, workspaceSlug]);

  useEffect(() => {
    if (!isOpen) return;
    void fetchSyncRuns();
  }, [isOpen, workspaceSlug]);

  useEffect(() => {
    if (!isOpen) return;
    const latestRun = syncRuns[0];
    if (!latestRun || !["pending", "running"].includes(latestRun.status)) return;

    const interval = setInterval(() => {
      void fetchSyncRuns().then(() => fetchContacts());
    }, 3000);
    return () => clearInterval(interval);
  }, [isOpen, syncRuns, workspaceSlug]);

  const importableContacts = useMemo(
    () => contacts.filter((contact) => contact.open_id && contact.is_active && !contact.is_imported),
    [contacts]
  );

  const toggleContact = (openId: string) => {
    setSelectedOpenIds((current) =>
      current.includes(openId) ? current.filter((item) => item !== openId) : [...current, openId]
    );
  };

  const toggleAll = () => {
    if (selectedOpenIds.length === importableContacts.length) {
      setSelectedOpenIds([]);
      return;
    }
    setSelectedOpenIds(importableContacts.map((contact) => contact.open_id).filter(Boolean) as string[]);
  };

  const handleClose = () => {
    setQuery("");
    setContacts([]);
    setSyncRuns([]);
    setSelectedOpenIds([]);
    onClose();
  };

  const syncContacts = async () => {
    setIsSyncing(true);
    await workspaceLarkService
      .sync(workspaceSlug, { role })
      .then((syncRun) => {
        setSyncRuns((current) => [syncRun, ...current]);
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "Sync started",
          message: "Feishu contact sync is running in the background.",
        });
      })
      .catch(() =>
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Error",
          message: "Failed to start Feishu contact sync.",
        })
      )
      .finally(() => setIsSyncing(false));
  };

  const importContacts = async () => {
    if (!selectedOpenIds.length) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error",
        message: "Select at least one Feishu contact.",
      });
      return;
    }

    setIsImporting(true);
    await workspaceLarkService
      .importUsers(workspaceSlug, {
        user_ids: selectedOpenIds,
        user_id_type: "open_id",
        role,
      })
      .then((response) => {
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "Imported",
          message: `${response.stats.members_added ?? 0} Feishu contacts were added to this workspace.`,
        });
        onImported();
        handleClose();
      })
      .catch(() =>
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Error",
          message: "Failed to import Feishu contacts.",
        })
      )
      .finally(() => setIsImporting(false));
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={handleClose} position={EModalPosition.CENTER} width={EModalWidth.XXXL}>
      <div className="flex max-h-[80vh] flex-col">
        <div className="flex items-center justify-between gap-4 border-b border-subtle px-6 py-4">
          <div>
            <h3 className="text-18 font-medium">Import from Feishu</h3>
            <p className="mt-1 text-13 text-secondary">
              {selectedOpenIds.length} selected
              {syncRuns[0] ? ` · Last sync ${syncRuns[0].status}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="h-9 rounded border border-subtle bg-surface-1 px-2 text-13 text-primary outline-none"
              value={role}
              onChange={(event) => setRole(Number(event.target.value) as TLarkWorkspaceRole)}
            >
              {roleOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <Button variant="secondary" size="lg" onClick={syncContacts} loading={isSyncing}>
              Sync contacts
            </Button>
            <Button variant="secondary" size="lg" onClick={handleClose} disabled={isImporting}>
              Cancel
            </Button>
            <Button variant="primary" size="lg" onClick={importContacts} loading={isImporting}>
              Import
            </Button>
          </div>
        </div>
        <div className="border-b border-subtle px-6 py-3">
          <div className="flex h-9 items-center gap-2 rounded-md border border-subtle bg-surface-1 px-3">
            <SearchIcon className="h-3.5 w-3.5 text-placeholder" />
            <input
              className="w-full border-none bg-transparent text-13 outline-none placeholder:text-placeholder"
              placeholder="Search Feishu contacts"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </div>
        <div className="min-h-[320px] overflow-y-auto px-6 py-4">
          {isLoading ? (
            <Loader className="space-y-3">
              <Loader.Item height="44px" />
              <Loader.Item height="44px" />
              <Loader.Item height="44px" />
              <Loader.Item height="44px" />
            </Loader>
          ) : (
            <div className="flex flex-col">
              {importableContacts.length > 0 && (
                <button
                  type="button"
                  className="mb-2 flex h-9 items-center gap-3 rounded px-2 text-left text-13 text-secondary hover:bg-surface-2"
                  onClick={toggleAll}
                >
                  <span onClick={(event) => event.stopPropagation()}>
                    <Checkbox checked={selectedOpenIds.length === importableContacts.length} onChange={toggleAll} />
                  </span>
                  Select all visible contacts
                </button>
              )}
              {contacts.map((contact) => {
                const openId = contact.open_id || "";
                const isDisabled = !openId || !contact.is_active || contact.is_imported;
                return (
                  <button
                    key={openId || contact.union_id || contact.name}
                    type="button"
                    className="flex h-14 items-center gap-3 rounded px-2 text-left hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={isDisabled}
                    onClick={() => toggleContact(openId)}
                  >
                    <span onClick={(event) => event.stopPropagation()}>
                      <Checkbox
                        checked={selectedOpenIds.includes(openId)}
                        onChange={() => toggleContact(openId)}
                        disabled={isDisabled}
                      />
                    </span>
                    <Avatar name={contact.name} src={contact.avatar || undefined} size="md" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-13 font-medium text-primary">{contact.name}</div>
                      <div className="truncate text-12 text-secondary">
                        {contact.email || contact.employee_no || contact.open_id}
                      </div>
                    </div>
                    <div className="w-24 text-right text-12 text-tertiary">
                      {contact.is_imported ? "Imported" : contact.is_active ? "" : "Inactive"}
                    </div>
                  </button>
                );
              })}
              {!contacts.length && (
                <div className="flex h-48 items-center justify-center text-13 text-secondary">
                  No Feishu contacts found.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </ModalCore>
  );
}

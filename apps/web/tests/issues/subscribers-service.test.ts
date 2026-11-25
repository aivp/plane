/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { beforeEach, describe, expect, test, vi } from "vitest";
import { IssueService } from "../../core/services/issue/issue.service";

const requests = vi.hoisted(() => ({ post: vi.fn(), delete: vi.fn() }));
vi.mock("@plane/constants", () => ({ API_BASE_URL: "" }));
vi.mock("@/services/api.service", () => ({
  APIService: class {
    post = requests.post;
    delete = requests.delete;
  },
}));

describe("updating work item subscribers", () => {
  const service = new IssueService();
  const url = "/api/workspaces/ws/projects/p/issues/i/issue-subscribers/";

  beforeEach(() => vi.resetAllMocks());

  test("sends only the changed memberships and skips duplicate selections", async () => {
    await service.updateSubscribers("ws", "p", "i", ["keep", "remove"], ["keep", "add", "add"]);
    expect(requests.post.mock.calls).toEqual([[url, { subscriber: "add" }]]);
    expect(requests.delete.mock.calls).toEqual([[`${url}remove/`]]);
  });

  test("waits for remaining writes after a failure so the list can be reloaded accurately", async () => {
    const error = new Error("Member left the project");
    requests.post.mockRejectedValue(error);
    let finishRemoval!: () => void;
    requests.delete.mockReturnValue(new Promise<void>((resolve) => (finishRemoval = resolve)));

    const onFailure = vi.fn();
    const update = service.updateSubscribers("ws", "p", "i", ["remove"], ["add"]).catch(onFailure);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(onFailure).not.toHaveBeenCalled();
    finishRemoval();
    await update;
    expect(onFailure).toHaveBeenCalledWith(error);
  });
});

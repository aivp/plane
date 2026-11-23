import { describe, expect, test, vi } from "vitest";
import { WorkspaceService } from "../../core/services/workspace.service";

const { get } = vi.hoisted(() => ({ get: vi.fn(async () => ({ data: { results: [] } })) }));
vi.mock("@plane/constants", () => ({ API_BASE_URL: "" }));
vi.mock("@/services/api.service", () => ({
  APIService: class {
    get = get;
  },
}));

describe("工作区任务入口", () => {
  test.each([
    ["my-todos", {}, "my-todos"],
    ["my-todos", { cursor: "1:1:0", expand: "issue_relation" }, "my-todos"],
    ["assigned", {}, "issues"],
    ["all-issues", { expand: "issue_relation" }, "issues-detail"],
  ] as const)("视图 %s 的请求参数 %o 转到 %s", async (view, params, endpoint) => {
    // 同一待办链接在翻页时仍由后端会话决定身份，其他视图沿用原入口。
    await new WorkspaceService().getViewIssues("team", view, params);
    expect(get).toHaveBeenLastCalledWith(`/api/workspaces/team/${endpoint}/`, { params }, {});
  });
});

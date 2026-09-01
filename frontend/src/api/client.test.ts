import { describe, it, expect } from "vitest";
import { buildChatUrl } from "./client";

describe("buildChatUrl", () => {
  it("prepends /api/v1", () => {
    expect(buildChatUrl()).toBe("/api/v1/chat");
  });
});

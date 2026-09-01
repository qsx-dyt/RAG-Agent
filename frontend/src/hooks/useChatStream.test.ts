import { describe, it, expect } from "vitest";
import { parseSSE } from "./useChatStream";

describe("parseSSE", () => {
  it("splits event blocks", () => {
    const chunk = "event: token\ndata: {\"text\":\"hi\"}\n\nevent: done\ndata: {}\n\n";
    const events: Array<{ event: string; data: string }> = [];
    parseSSE(chunk, (e) => events.push(e));
    expect(events).toHaveLength(2);
    expect(events[0].event).toBe("token");
    expect(JSON.parse(events[0].data).text).toBe("hi");
  });
});

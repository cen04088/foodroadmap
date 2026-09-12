import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchMealRecommendations } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("meal recommendation requests", () => {
  it("sends the server context and previous preferences, with an abort signal", async () => {
    const result = { recommendations: [], preferences: {}, reply: "조건을 바꿔보세요" };
    const mock = vi.fn().mockResolvedValue({ ok: true, json: async () => result });
    vi.stubGlobal("fetch", mock);
    const controller = new AbortController();
    const request = { route_context_id: "context", message: "더 일찍", previous: null };
    expect(await fetchMealRecommendations(request, controller.signal, "http://localhost:8000")).toEqual(result);
    expect(mock.mock.calls[0][0]).toBe("http://localhost:8000/api/meal-recommendations");
    expect(JSON.parse(mock.mock.calls[0][1].body)).toEqual(request);
    expect(mock.mock.calls[0][1].signal).toBe(controller.signal);
  });

  it("preserves the expiry message so the user knows to search again", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 410, json: async () => ({ detail: "경로가 만료됐어요" }) }));
    await expect(fetchMealRecommendations({ route_context_id: "context", message: "한식", previous: null }))
      .rejects.toMatchObject({ status: 410, message: "경로가 만료됐어요" });
  });

  it("handles non-JSON proxy errors without showing raw HTML", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => { throw new Error("html"); } }));
    await expect(fetchMealRecommendations({ route_context_id: "context", message: "한식", previous: null })).rejects.toBeInstanceOf(ApiError);
  });

  it("propagates cancellation instead of relabeling it as a network failure", async () => {
    const controller = new AbortController();
    controller.abort();
    const abort = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
    await expect(fetchMealRecommendations({ route_context_id: "context", message: "한식", previous: null }, controller.signal)).rejects.toBe(abort);
  });
});

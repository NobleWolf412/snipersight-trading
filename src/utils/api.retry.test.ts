import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./debugLogger', () => ({ debugLogger: { api: vi.fn(), info: vi.fn(), warning: vi.fn(), error: vi.fn(), success: vi.fn() } }));
beforeEach(() => { vi.resetModules(); vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('request retry boundaries', () => {
  it.each(['POST', 'PUT', 'PATCH', 'DELETE'])('sends %s once even when retry is requested', async method => {
    const fetcher = vi.fn().mockResolvedValue(new Response('{"detail":"response uncertain"}', {status:503}));
    vi.stubGlobal('fetch', fetcher);
    const { api } = await import('./api');
    const result = await (api as any).request('/test-command', {method, maxRetries:3, silent:true});
    expect(result.error).toBeTruthy();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('does not retry a read by default and allows an explicit read retry', async () => {
    const fetcher=vi.fn().mockResolvedValue(new Response('{"detail":"offline"}', {status:503}));
    vi.stubGlobal('fetch',fetcher);
    const { api }=await import('./api');
    expect((await api.getBotStatus()).error).toBeTruthy();
    expect(fetcher).toHaveBeenCalledTimes(1);
    fetcher.mockResolvedValueOnce(new Response('{"detail":"temporary"}', {status:503}))
      .mockResolvedValueOnce(new Response('{"status":"idle"}', {status:200,headers:{'Content-Type':'application/json'}}));
    const pending=(api as any).request('/test-read',{maxRetries:1,silent:true});
    await vi.advanceTimersByTimeAsync(2000);
    expect((await pending).data).toEqual({status:'idle'});
    expect(fetcher).toHaveBeenCalledTimes(3);
  });
});

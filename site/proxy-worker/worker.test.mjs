import assert from 'node:assert/strict';
import { test } from 'node:test';
import worker from './worker.mjs';

test('proxies each path to the published Sites origin', async () => {
  const originalFetch = globalThis.fetch;
  let upstreamRequest;
  globalThis.fetch = async request => {
    upstreamRequest = request;
    return new Response('Qiming page', { status: 200, headers: { 'content-type': 'text/html' } });
  };
  try {
    const inbound = new Request('https://qiming.dashen.wang/ja/?topic=skill', {
      headers: { 'accept-language': 'ja' },
    });
    const response = await worker.fetch(inbound);
    assert.equal(upstreamRequest.url, 'https://qiming-skill.y4nssss.chatgpt.site/ja/?topic=skill');
    assert.equal(upstreamRequest.headers.get('accept-language'), 'ja');
    assert.equal(response.status, 200);
    assert.equal(await response.text(), 'Qiming page');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

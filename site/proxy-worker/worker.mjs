const UPSTREAM_ORIGIN = 'https://qiming-skill.y4nssss.chatgpt.site';

export default {
  async fetch(request) {
    const upstreamUrl = new URL(request.url);
    const origin = new URL(UPSTREAM_ORIGIN);
    upstreamUrl.protocol = origin.protocol;
    upstreamUrl.host = origin.host;
    return fetch(new Request(upstreamUrl, request));
  },
};

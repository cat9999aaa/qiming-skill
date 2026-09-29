# Qiming website

Live site: https://qiming.dashen.wang/

The official site is a dependency-free static build. `content.json` contains four localized editions: Simplified Chinese (root), Traditional Chinese (`/zh-TW/`), Japanese (`/ja/`), and English (`/en/`). `assets/` contains the original Qiming logo, favicon, styles, and copy interaction.

Build and preview locally:

```sh
python3 site/build.py
python3 -m http.server 8765 --directory site/dist
```

Open `http://localhost:8765/`. The local preview reads `site/release.json`. The public repository is `https://github.com/cat9999aaa/qiming-skill`; the installation section builds its command and copyable Agent prompt from that URL.

For another release source, change `repo_url` in `site/release.json` and rebuild. A null URL shows a pending state without a broken command. `--repo-url` overrides the local release setting for test builds. The `site_url` setting controls canonical, multilingual alternate and sitemap URLs; set it to the public HTTPS origin before publishing.

Source inspiration: [Omarchy's homepage](https://omarchy.us/) for its direct hero-to-install structure. The colors, logo, control-panel motif, and copy are original to Qiming and do not use Evangelion or NERV assets.

## Production hosting

The official domain `https://qiming.dashen.wang/` is hosted directly on Cloudflare Pages project `qiming-skill`. Its DNS record is a proxied (orange-cloud) CNAME to `qiming-skill.pages.dev`. The build output is `site/dist/`; upload its contents, with `index.html` at the root, for each release. The earlier ChatGPT Sites address is a secondary published copy, not the origin for this domain. Rebuild the static files before publishing so canonical, `hreflang`, robots and sitemap URLs continue to point at the official domain.

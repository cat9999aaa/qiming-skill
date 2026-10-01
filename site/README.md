# Qiming website

Live site: https://qiming.dashen.wang/

The official site is a dependency-free static build. `content.json` retains the four existing localized editions; `page_content.json` contains topic-level metadata, navigation, the self-managed site case, and the sanitized field report. `fit_content.json` provides plain-language fit and non-fit boundaries in all four languages. `articles/why-qiming.zh-CN.md` is the full Simplified Chinese introduction, rendered on `/how/`; other languages link to it with its language stated. Simplified Chinese uses the root URL; Traditional Chinese uses `/zh-TW/`, Japanese `/ja/`, and English `/en/`. Each locale has separate pages for getting started, how it works, domains, cases, prompts, feedback, story, updates, FAQ, and a More menu. `assets/` contains the Qiming logo, favicon, pixel-inspired styles, and copy interaction.

Build and preview locally:

```sh
python3 site/build.py
python3 -m http.server 8765 --directory site/dist
```

Open `http://localhost:8765/` and `http://localhost:8765/start/`. The local preview reads `site/release.json`. The public repository is `https://github.com/cat9999aaa/qiming-skill`; the start page builds its command and copyable Agent prompt from that URL.

For another release source, change `repo_url` in `site/release.json` and rebuild. A null URL shows a pending state without a broken command. `--repo-url` overrides the local release setting for test builds. The `site_url` setting controls canonical, multilingual alternate and sitemap URLs; set it to the public HTTPS origin before publishing.

Source inspiration: [Omarchy's homepage](https://omarchy.us/) for its direct value-to-action structure. The pixel grid, cards, colors, logo, and copy are original to Qiming and do not use Omarchy, Evangelion, or NERV assets.

## Search and content maintenance

Each topic has its own canonical URL, description, visible `h1`, four-language alternate links, JSON-LD for visible entities, and sitemap entry. `robots.txt` allows public crawlers, including OAI-SearchBot. These help pages be discovered and understood; they do not guarantee search ranking or AI citations. Update the relevant content files when a topic changes. The long article is edited as Markdown and rendered with the site's small dependency-free block renderer. Keep field reports labeled with attribution, sample size, and limits; never publish private project paths, domains, machine identifiers, or credentials.

## Production hosting

The official domain `https://qiming.dashen.wang/` is hosted directly on Cloudflare Pages project `qiming-skill`. Its DNS record is a proxied (orange-cloud) CNAME to `qiming-skill.pages.dev`. The build output is `site/dist/`; upload its contents, with `index.html` at the root, for each release. The earlier ChatGPT Sites address is a secondary published copy, not the origin for this domain. Rebuild the static files before publishing so canonical, `hreflang`, robots and sitemap URLs continue to point at the official domain.

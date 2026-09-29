#!/usr/bin/env python3
"""Build the multilingual, dependency-free Qiming site."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


HERE = Path(__file__).resolve().parent
LOCALES = {"zh-CN": "/", "zh-TW": "/zh-TW/", "ja": "/ja/", "en": "/en/"}
SECTION_IDS = ("method", "beginner", "examples", "prompts", "story", "changelog", "install")


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def repo_slug(url: str | None) -> str | None:
    if url is None:
        return None
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/?", url)
    if not match:
        raise ValueError("repo URL must be a GitHub owner/repository URL")
    return match.group(1)


def copy_button(value: str, label: str, copied: str, extra_class: str = "") -> str:
    return (
        f'<button class="copy-button {extra_class}" type="button" '
        f'data-copy="{esc(value)}" data-default-label="{esc(label)}" '
        f'data-copied-label="{esc(copied)}" aria-label="{esc(label)}">'
        f'<span class="copy-symbol" aria-hidden="true">⧉</span><span>{esc(label)}</span></button>'
    )


def validate_site_url(site_url: str) -> str:
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+", site_url):
        raise ValueError("site URL must be an HTTPS origin without a path")
    return site_url


def render(locale: str, t: dict, repo_url: str | None, site_url: str) -> str:
    root = LOCALES[locale]
    canonical = site_url + root
    asset = "assets" if root == "/" else "../assets"
    nav = "".join(
        f'<a href="#{section}">{esc(label)}</a>'
        for section, label in zip(SECTION_IDS, t["nav"], strict=True)
    )
    langs = "".join(
        f'<a href="{url}" hreflang="{code}" lang="{code}" '
        f'{"aria-current=\"page\"" if code == locale else ""}>{esc({"zh-CN": "简中", "zh-TW": "繁中", "ja": "日本語", "en": "EN"}[code])}</a>'
        for code, url in LOCALES.items()
    )
    alternate = "".join(
        f'<link rel="alternate" hreflang="{code}" href="{esc(site_url + url)}">'
        for code, url in LOCALES.items()
    ) + f'<link rel="alternate" hreflang="x-default" href="{esc(site_url)}/">'
    methods = "".join(
        f'<article class="method-card"><span class="step-index">{esc(item["number"])}</span>'
        f'<div class="step-mark" aria-hidden="true">↳</div><h3>{esc(item["title"])}</h3>'
        f'<p>{esc(item["body"])}</p></article>'
        for item in t["methods"]
    )
    beginner_steps = "".join(
        f'<article class="beginner-step"><span class="step-index">{esc(item["number"])}</span>'
        f'<h3>{esc(item["title"])}</h3><p>{esc(item["body"])}</p></article>'
        for item in t["beginner_steps"]
    )
    real_cases = "".join(
        f'<article class="real-case"><div class="real-case-head"><span>{esc(item["category"])}</span>'
        f'<span class="real-status">{esc(item["status"])}</span></div>'
        f'<h3>{esc(item["title"])}</h3>'
        + "".join(
            f'<div class="real-fact"><b>{esc(label)}</b><p>{esc(fact)}</p></div>'
            for label, fact in zip(t["real_field_labels"], item["facts"], strict=True)
        )
        + f'<div class="real-prompt"><b>{esc(t["real_prompt_label"])}</b><p>{esc(item["prompt"])}</p>'
        f'{copy_button(item["prompt"], t["prompt_copy"], t["prompt_copied"])}</div></article>'
        for item in t["real_cases"]
    )
    chips = "".join(f"<span>{esc(chip)}</span>" for chip in t["member_chips"])
    examples = "".join(
        f'<article class="example-card"><div class="card-top"><span class="tiny-number">0{i}</span>'
        f'<span class="card-category">{esc(item["category"])}</span></div>'
        f'<h3>{esc(item["title"])}</h3>'
        f'<div class="example-quote"><span>{esc(t["example_prompt"])}</span><p>{esc(item["prompt"])}</p></div>'
        f'<div class="example-result"><b>{esc(t["example_result"])}</b><p>{esc(item["result"])}</p></div>'
        f'{copy_button(item["prompt"], t["prompt_copy"], t["prompt_copied"])}</article>'
        for i, item in enumerate(t["examples"], start=1)
    )
    prompts = "".join(
        f'<article class="prompt-row"><div><span class="tiny-number">0{i}</span>'
        f'<h3>{esc(item["title"])}</h3></div><p>{esc(item["body"])}</p>'
        f'{copy_button(item["body"], t["prompt_copy"], t["prompt_copied"])}</article>'
        for i, item in enumerate(t["prompts"], start=1)
    )
    story = "".join(f"<p>{esc(p)}</p>" for p in t["story_paragraphs"])
    faq = "".join(
        f'<article class="faq-item"><h3>{esc(item["question"])}</h3><p>{esc(item["answer"])}</p></article>'
        for item in t["faq_items"]
    )
    changes = "".join(
        f'<article class="change-row"><time datetime="{item["date"].replace(".", "-")}">{esc(item["date"])}</time>'
        f'<div><h3>{esc(item["title"])}</h3><p>{esc(item["body"])}</p></div></article>'
        for item in t["changes"]
    )
    slug = repo_slug(repo_url)
    if slug:
        command = f"npx skills add {slug} --skill qiming"
        agent_prompt = t["install_agent_template"].replace("{repo_url}", repo_url)
        install_content = (
            f'<div class="install-part"><span class="install-kicker">{esc(t["install_command"])}</span>'
            f'<div class="command-line"><code>{esc(command)}</code>'
            f'{copy_button(command, t["prompt_copy"], t["prompt_copied"])}</div></div>'
            f'<div class="install-part"><span class="install-kicker">{esc(t["install_prompt"])}</span>'
            f'<div class="prompt-install"><p>{esc(agent_prompt)}</p>'
            f'{copy_button(agent_prompt, t["prompt_copy"], t["prompt_copied"])}</div></div>'
            f'<a class="source-link" href="{esc(repo_url)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(t["install_source"])} <span aria-hidden="true">↗</span></a>'
        )
    else:
        install_content = f'<div class="install-pending" role="status"><span class="status-dot"></span>{esc(t["install_pending"])}</div>'
    footer_links = "".join(
        f'<a href="#{section}">{esc(label)}</a>'
        for section, label in zip(("method", "examples", "story", "changelog", "install"), t["footer_links"], strict=True)
    )
    title_lines = "<br>".join(esc(line) for line in t["hero_lines"][:2])
    title_lines += f'<br><em>{esc(t["hero_lines"][2])}</em>'
    panel_files = "".join(f"<li>{esc(item)}</li>" for item in t["panel_files"])
    panel_units = "".join(f"<span>{esc(item)}</span>" for item in t["panel_units"])
    graph = [
        {"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical,
         "name": t["title"], "description": t["description"], "inLanguage": locale,
         "isPartOf": {"@id": site_url + "/#website"}},
        {"@type": "WebSite", "@id": site_url + "/#website", "url": site_url + "/",
         "name": "启明 Qiming", "inLanguage": list(LOCALES)},
    ]
    if repo_url:
        graph.append({"@type": "SoftwareSourceCode", "@id": site_url + "/#skill",
                      "name": "启明 Qiming Skill", "description": t["description"],
                      "url": site_url + "/", "codeRepository": repo_url,
                      "license": repo_url + "/blob/main/LICENSE",
                      "programmingLanguage": ["Python", "Markdown"],
                      "isAccessibleForFree": True})
        graph[0]["about"] = {"@id": site_url + "/#skill"}
    structured_data = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="{locale}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#120f16">
  <meta name="description" content="{esc(t['description'])}">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="启明 Qiming">
  <meta property="og:title" content="{esc(t['title'])}">
  <meta property="og:description" content="{esc(t['description'])}">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:locale" content="{ {'zh-CN': 'zh_CN', 'zh-TW': 'zh_TW', 'ja': 'ja_JP', 'en': 'en_US'}[locale] }">
  <title>{esc(t['title'])}</title>
  <link rel="icon" href="{asset}/favicon.ico" sizes="any">
  <link rel="icon" href="{asset}/logo.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{asset}/style.css">
  {alternate}
  <script type="application/ld+json">{structured_data}</script>
  <script src="{asset}/app.js" defer></script>
</head>
<body>
  <a class="skip-link" href="#main">{esc(t['skip'])}</a>
  <div class="signal-strip"><span>QIMING // PROJECT SYSTEM</span><span>001 <i></i> READY</span></div>
  <header class="site-header" id="top">
    <div class="header-inner wrap">
      <a class="brand" href="/" aria-label="Qiming"><img src="{asset}/logo.svg" width="42" height="42" alt=""><span><b>启明</b><small>QIMING</small></span></a>
      <nav class="main-nav" aria-label="Main">{nav}</nav>
      <div class="header-right"><div class="language-menu"><span>{esc(t['language'])}</span><div>{langs}</div></div><a class="header-cta" href="#install">{esc(t['header_cta'])}<span aria-hidden="true">↗</span></a></div>
    </div>
  </header>
  <main id="main">
    <section class="hero wrap">
      <div class="hero-copy">
        <div class="eyebrow"><span class="signal-dot"></span>{esc(t['hero_tag'])}</div>
        <h1>{title_lines}</h1>
        <p class="hero-lead">{esc(t['hero_lead'])}</p>
        <div class="hero-actions"><a class="button button-primary" href="#install">{esc(t['hero_primary'])}<span aria-hidden="true">↗</span></a><a class="button button-outline" href="#examples">{esc(t['hero_secondary'])}<span aria-hidden="true">↘</span></a></div>
        <p class="hero-note"><span aria-hidden="true">▸</span> {esc(t['hero_note'])}</p>
      </div>
      <div class="hero-diagram" aria-label="Qiming workspace diagram">
        <div class="diagram-top"><span>{esc(t['panel_top'])}</span><b><span class="signal-dot"></span>{esc(t['panel_status'])}</b></div>
        <div class="diagram-body">
          <div class="diagram-source"><span class="diagram-index">01 / INPUT</span><h2>{esc(t['panel_source'])}</h2><ul>{panel_files}</ul></div>
          <div class="diagram-flow"><i></i><span>{esc(t['panel_arrow'])}</span><i></i></div>
          <div class="diagram-instance"><span class="diagram-index">02 / OUTPUT</span><h2>{esc(t['panel_instance'])}</h2><div class="diagram-units">{panel_units}</div></div>
        </div>
        <div class="diagram-footer"><span>{esc(t['panel_footer'])}</span><span>Q/01</span></div>
      </div>
    </section>
    <section class="statement"><div class="wrap"><span class="statement-glyph" aria-hidden="true">※</span><p>{esc(t['statement'])}</p><span class="statement-arrow" aria-hidden="true">↗</span></div></section>
    <section class="section method-section" id="method"><div class="wrap">
      <div class="section-head"><span class="section-label">{esc(t['method_label'])}</span><div><h2>{esc(t['method_title'])}</h2><p>{esc(t['method_intro'])}</p></div></div>
      <div class="method-grid">{methods}</div>
      <div class="member-panel"><div class="member-mark" aria-hidden="true">Q<span>+</span></div><div><span class="section-label">{esc(t['member_label'])}</span><h3>{esc(t['member_title'])}</h3><p>{esc(t['member_body'])}</p><div class="member-chips">{chips}</div></div></div>
    </div></section>
    <section class="section beginner-section" id="beginner"><div class="wrap"><div class="section-head"><span class="section-label">{esc(t['beginner_label'])}</span><div><h2>{esc(t['beginner_title'])}</h2><p>{esc(t['beginner_intro'])}</p></div></div><div class="beginner-grid">{beginner_steps}</div><div class="beginner-prompt"><div><b>{esc(t['beginner_prompt_label'])}</b><p>{esc(t['beginner_prompt'])}</p></div>{copy_button(t['beginner_prompt'], t['prompt_copy'], t['prompt_copied'])}</div></div></section>
    <section class="section examples-section" id="examples"><div class="wrap"><div class="section-head"><span class="section-label">{esc(t['examples_label'])}</span><div><h2>{esc(t['examples_title'])}</h2><p>{esc(t['examples_intro'])}</p></div></div><div class="real-case-grid">{real_cases}</div><div class="example-grid">{examples}</div></div></section>
    <section class="section prompts-section" id="prompts"><div class="wrap"><div class="section-head"><span class="section-label">{esc(t['prompts_label'])}</span><div><h2>{esc(t['prompts_title'])}</h2><p>{esc(t['prompts_intro'])}</p></div></div><div class="prompt-list">{prompts}</div></div></section>
    <section class="section faq-section" id="faq"><div class="wrap"><div class="section-head"><span class="section-label">{esc(t['faq_label'])}</span><div><h2>{esc(t['faq_title'])}</h2><p>{esc(t['faq_intro'])}</p></div></div><div class="faq-grid">{faq}</div></div></section>
    <section class="section story-section" id="story"><div class="wrap story-layout"><div><span class="section-label">{esc(t['story_label'])}</span><h2>{esc(t['story_title'])}</h2><div class="story-symbol" aria-hidden="true"><span>Q</span><i></i></div></div><div class="story-text">{story}</div></div></section>
    <section class="section changelog-section" id="changelog"><div class="wrap"><div class="section-head"><span class="section-label">{esc(t['changelog_label'])}</span><div><h2>{esc(t['changelog_title'])}</h2></div></div><div class="change-list">{changes}</div></div></section>
    <section class="section install-section" id="install"><div class="wrap install-layout"><div class="install-intro"><span class="section-label">{esc(t['install_label'])}</span><h2>{esc(t['install_title'])}</h2><p>{esc(t['install_intro'])}</p><div class="install-glyph" aria-hidden="true">↘</div></div><div class="install-box"><div class="install-box-head"><span>QIMING / INSTALL TERMINAL</span><span class="status-dot"></span></div>{install_content}<div class="install-adopt"><span>{esc(t['install_after'])}</span><p>{esc(t['install_adopt'])}</p>{copy_button(t['install_adopt'], t['prompt_copy'], t['prompt_copied'])}</div><p class="install-note">{esc(t['install_note'])}</p></div></div></section>
  </main>
  <footer class="site-footer"><div class="wrap footer-main"><div><a class="brand" href="/"><img src="{asset}/logo.svg" width="42" height="42" alt=""><span><b>启明</b><small>QIMING</small></span></a><p>{esc(t['footer_line'])}</p></div><nav aria-label="Footer">{footer_links}</nav></div><div class="wrap footer-bottom"><span>© 2026 QIMING</span><span>{esc(t['footer_status'])}</span><a href="#top">↑ TOP</a></div></footer>
</body>
</html>
"""


def sitemap(site_url: str) -> str:
    alternates = "".join(
        f'    <xhtml:link rel="alternate" hreflang="{code}" href="{xml_escape(site_url + route)}"/>\n'
        for code, route in LOCALES.items()
    ) + f'    <xhtml:link rel="alternate" hreflang="x-default" href="{xml_escape(site_url)}/"/>\n'
    entries = "".join(
        f'  <url>\n    <loc>{xml_escape(site_url + route)}</loc>\n{alternates}  </url>\n'
        for route in LOCALES.values()
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            f'{entries}</urlset>\n')


def build(out: Path, repo_url: str | None, site_url: str) -> None:
    repo_slug(repo_url)
    validate_site_url(site_url)
    content = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
    if set(content) != set(LOCALES):
        raise ValueError("site content must contain exactly four supported locales")
    for locale, route in LOCALES.items():
        page = out if route == "/" else out / locale
        page.mkdir(parents=True, exist_ok=True)
        (page / "index.html").write_text(render(locale, content[locale], repo_url, site_url), encoding="utf-8")
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("style.css", "app.js", "logo.svg", "favicon.ico"):
        shutil.copyfile(HERE / "assets" / name, assets / name)
    (out / "release.json").write_text(
        json.dumps({"repo_url": repo_url, "site_url": site_url, "published": bool(repo_url)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nUser-agent: OAI-SearchBot\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n",
        encoding="utf-8",
    )
    (out / "sitemap.xml").write_text(sitemap(site_url), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "dist")
    parser.add_argument("--repo-url")
    parser.add_argument("--site-url")
    args = parser.parse_args()
    release = json.loads((HERE / "release.json").read_text(encoding="utf-8"))
    build(args.out, args.repo_url or release["repo_url"], args.site_url or release["site_url"])


if __name__ == "__main__":
    main()

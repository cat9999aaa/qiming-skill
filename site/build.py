#!/usr/bin/env python3
"""Build the four-language, multi-page Qiming website with the standard library."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


HERE = Path(__file__).resolve().parent
LOCALES = {"zh-CN": "", "zh-TW": "zh-TW", "ja": "ja", "en": "en"}
PAGES = ("home", "start", "how", "domains", "cases", "articles", "prompts", "feedback", "story", "updates", "faq", "more")
MAIN_NAV = ("home", "start", "how", "domains", "cases", "articles", "prompts", "feedback")
MOBILE_NAV = ("home", "start", "domains", "articles", "more")
MORE_NAV = ("cases", "prompts", "feedback", "story", "updates", "faq")
LANG_LABELS = {"zh-CN": "简中", "zh-TW": "繁中", "ja": "日本語", "en": "EN"}
OG_LOCALES = {"zh-CN": "zh_CN", "zh-TW": "zh_TW", "ja": "ja_JP", "en": "en_US"}


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def asset_url(name: str) -> str:
    """Give changed static files a new URL so cached CSS/JS cannot outlive HTML."""
    if name not in {"style.css", "app.js"}:
        raise ValueError("unsupported versioned asset")
    digest = hashlib.sha256((HERE / "assets" / name).read_bytes()).hexdigest()[:12]
    return f"/assets/{name}?v={digest}"


def route(locale: str, page: str = "home") -> str:
    parts = ([LOCALES[locale]] if LOCALES[locale] else []) + ([page] if page != "home" else [])
    return "/" + "/".join(parts) + ("/" if parts else "")


def article_route(locale: str, slug: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("invalid article slug")
    return route(locale, "articles") + slug + "/"


def article_catalog() -> list[dict]:
    items = json.loads((HERE / "articles" / "catalog.json").read_text(encoding="utf-8"))["items"]
    if not items or len({item["slug"] for item in items}) != len(items):
        raise ValueError("article catalog needs unique entries")
    for item in items:
        article_route("zh-CN", item["slug"])
        if item["default_locale"] not in item["source"]:
            raise ValueError("article default locale needs full text")
        for locale, filename in item["source"].items():
            if locale not in LOCALES or Path(filename).name != filename or not (HERE / "articles" / filename).is_file():
                raise ValueError("invalid article source")
        for key in ("title", "summary", "availability", "read_label"):
            if set(item[key]) != set(LOCALES):
                raise ValueError("article metadata must cover four locales")
    return items


def repo_slug(url: str | None) -> str | None:
    if url is None:
        return None
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/?", url)
    if not match:
        raise ValueError("repo URL must be a GitHub owner/repository URL")
    return match.group(1)


def validate_site_url(site_url: str) -> str:
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+", site_url):
        raise ValueError("site URL must be an HTTPS origin without a path")
    return site_url


def copy_button(value: str, t: dict) -> str:
    label, copied = t["prompt_copy"], t["prompt_copied"]
    return (f'<button class="copy-button" type="button" data-copy="{e(value)}" '
            f'data-default-label="{e(label)}" data-copied-label="{e(copied)}" '
            f'aria-label="{e(label)}"><span aria-hidden="true">⧉</span><span>{e(label)}</span></button>')


def link(locale: str, page: str, label: str, css: str = "") -> str:
    return f'<a class="{e(css)}" href="{route(locale, page)}">{e(label)} <span aria-hidden="true">↗</span></a>'


def link_card(locale: str, page: str, p: dict, index: int) -> str:
    return (f'<a class="pixel-card link-card" href="{route(locale, page)}"><span class="pixel-index">0{index}</span>'
            f'<h2>{e(p["labels"][page])}</h2><p>{e(p["summary"][page])}</p>'
            f'<span class="link-arrow" aria-hidden="true">↗</span></a>')


def fit_panel(fit: dict, article_href: str) -> str:
    columns = []
    for key, section_id in (("fit", "fit-boundary"), ("not_fit", "not-fit-boundary")):
        points = "".join(f'<li>{e(item)}</li>' for item in fit[key + "_points"])
        columns.append(f'<article class="pixel-card fit-card" id="{section_id}"><h2>{e(fit[key + "_title"])}</h2>'
                       f'<p>{e(fit[key + "_body"])}</p><ul>{points}</ul></article>')
    return (f'<section class="page-section wrap fit-section"><div class="fit-grid">{"".join(columns)}</div>'
            f'<p class="guide-link-row" id="full-guide"><a href="{e(article_href)}">{e(fit["long_label"])} ↗</a>'
            f'<span>{e(fit["long_note"])}</span></p></section>')


def article_inline(value: str) -> str:
    pieces = re.split(r"(`[^`]+`|https://[^\s，。]+)", value)
    return "".join(f'<code>{e(piece[1:-1])}</code>' if piece.startswith("`") and piece.endswith("`") else
                   f'<a href="{e(piece)}" rel="noopener noreferrer">{e(piece)}</a>'
                   if piece.startswith("https://") else e(piece) for piece in pieces)


def longform_article(item: dict, locale: str, labels: dict, articles: list[dict]) -> str:
    """Render one catalogued Markdown article without a runtime dependency."""
    source = (HERE / "articles" / item["source"][locale]).read_text(encoding="utf-8")
    lines = source.splitlines()
    headings: list[tuple[str, str]] = []
    section_number = 0
    for line in lines:
        if line.startswith("## "):
            section_number += 1
            heading = line[3:]
            heading_id = ("guide-omarchy-ai" if "Omarchy" in heading else
                          "guide-pi-submember" if "Pi Agent" in heading else f"guide-section-{section_number}")
            headings.append((heading_id, heading))
    sections: list[str] = []
    paragraph: list[str] = []
    code: list[str] | None = None
    current_section = 0
    title: str | None = None

    def flush() -> None:
        if paragraph:
            sections.append(f'<p>{article_inline(" ".join(paragraph))}</p>')
            paragraph.clear()

    for line in lines:
        if code is not None:
            if line.startswith("```"):
                sections.append(f'<pre><code>{e(chr(10).join(code))}</code></pre>')
                code = None
            else:
                code.append(line)
        elif line.startswith("```"):
            flush()
            code = []
        elif not line.strip():
            flush()
        elif line.startswith("### "):
            flush()
            sections.append(f'<h3>{e(line[4:])}</h3>')
        elif line.startswith("## "):
            flush()
            heading_id, heading = headings[current_section]
            current_section += 1
            sections.append(f'<h2 id="{heading_id}">{e(heading)}</h2>')
        elif line.startswith("# "):
            flush()
            if title is not None:
                raise ValueError("longform article has multiple titles")
            title = line[2:]
        else:
            paragraph.append(line)
    flush()
    if code is not None:
        raise ValueError("unfinished code fence in longform article")
    if title is None:
        raise ValueError("longform article needs a title")
    toc = "".join(f'<a href="#{heading_id}">{e(heading)}</a>' for heading_id, heading in headings)
    series_links = []
    for index, other in enumerate(articles, 1):
        current = ' aria-current="page"' if other["slug"] == item["slug"] else ""
        series_links.append(
            f'<a href="{article_route(other["default_locale"], other["slug"])}"{current}>'
            f'<span>{index:02d}</span><strong>{e(other["title"]["zh-CN"])}</strong><span aria-hidden="true">↗</span></a>'
        )
    series = "".join(series_links)
    return (f'<section class="page-section wrap longform"><div class="article-heading">'
            f'<a href="{route(locale, "articles")}">← {e(labels["articles"])}</a>'
            f'<time datetime="{e(item["published"])}">{e(item["published"])}</time></div>'
            f'<header class="article-lead"><span class="eyebrow">QIMING / FIELD NOTES</span>'
            f'<h1 class="guide-title">{e(title)}</h1>'
            f'<p class="article-summary">{e(item["summary"][locale])}</p></header><div class="guide-layout">'
            f'<details class="guide-toc" open><summary>阅读目录 <span>{len(headings)} 节</span></summary>'
            f'<nav class="toc-links" aria-label="文章目录">{toc}</nav></details>'
            f'<article class="guide-prose">{"".join(sections)}</article></div>'
            f'<nav class="article-series" aria-label="系列文章"><h2>系列文章</h2>'
            f'<p>按主题继续读。每篇都标出管理动作与实际验证的边界。</p>'
            f'<div class="article-series-links">{series}</div></nav></section>')


def header(locale: str, page: str, p: dict) -> str:
    desktop = "".join(f'<a href="{route(locale, key)}"{(" aria-current=" + chr(34) + "page" + chr(34)) if key == page else ""}>{e(p["labels"][key])}</a>' for key in MAIN_NAV)
    icons = ("⌂", "✦", "▦", "▤", "···")
    mobile = "".join(
        f'<a href="{route(locale, key)}"{(" aria-current=" + chr(34) + "page" + chr(34)) if key == page else ""}>'
        f'<span class="mobile-icon" aria-hidden="true">{icon}</span><span>{e(p["labels"][key])}</span></a>'
        for key, icon in zip(MOBILE_NAV, icons, strict=True))
    languages = "".join(
        f'<a href="{route(code, page)}" lang="{code}" hreflang="{code}"'
        f'{(" aria-current=" + chr(34) + "page" + chr(34)) if code == locale else ""}>{e(label)}</a>'
        for code, label in LANG_LABELS.items())
    return (f'<div class="top-signal"><span>QIMING // YOUR WORKSPACE, CONTINUED</span><span>● LOCAL FIRST</span></div>'
            f'<header class="site-header" id="top"><div class="wrap header-inner">'
            f'<a class="brand" href="{route(locale)}"><img src="/assets/logo.svg" width="42" height="42" alt="">'
            f'<span><b>启明</b><small>QIMING SKILL</small></span></a>'
            f'<nav class="desktop-nav" aria-label="Primary">{desktop}</nav>'
            f'<div class="language-menu" aria-label="Languages">{languages}</div>'
            f'{link(locale, "start", p["labels"]["start"], "header-cta")}</div></header>'
            f'<nav class="mobile-nav" aria-label="Mobile">{mobile}</nav>')


def footer(locale: str, p: dict, t: dict) -> str:
    links = "".join(link(locale, key, p["labels"][key]) for key in ("start", "how", "domains", "cases", "articles", "prompts", "feedback", "story", "updates", "faq"))
    return (f'<footer class="site-footer"><div class="wrap footer-grid"><div>'
            f'<a class="brand" href="{route(locale)}"><img src="/assets/logo.svg" width="42" height="42" alt="">'
            f'<span><b>启明</b><small>QIMING SKILL</small></span></a><p>{e(t["footer_line"])}</p></div>'
            f'<nav aria-label="Footer">{links}</nav></div><div class="wrap footer-bottom">'
            f'<span>© 2026 QIMING</span><span>{e(t["footer_status"])}</span><a href="#top">↑ TOP</a></div></footer>')


def onboarding(locale):
    return json.loads((HERE / 'onboarding.json').read_text(encoding='utf-8'))[locale]


def before_after(locale):
    o=onboarding(locale)
    columns=''.join(f'<article class="pixel-card before-after-card"><h3>{e(o[key])}</h3><p>{e(o[key+"_note"])}</p><pre class="directory-tree"><code>{e(o["tree_"+key])}</code></pre></article>' for key in ('before','after'))
    return f'<section class="page-section wrap" id="before-after"><div class="section-heading"><span class="eyebrow">PROJECT / BEFORE + AFTER</span><h2>{e(o["title"])}</h2></div><div class="fit-grid">{columns}</div><aside class="pixel-card continuity-proof"><h3>{e(o["smoke_title"])}</h3><p>{e(o["smoke_body"])}</p></aside></section>'


def working_details(locale, article_href, fit):
    o=onboarding(locale)
    headings=''.join(f'<th scope="col">{e(x)}</th>' for x in o['compare_headers'])
    rows=''.join('<tr>'+''.join(f'<td>{e(x)}</td>' for x in row)+'</tr>' for row in o['compare_rows'])
    return (f'<section class="page-section wrap"><div class="section-heading"><h2>{e(o["flow_title"])}</h2></div>'
            f'<p class="flow-path">{e(o["flow"])}</p><p class="section-copy">{e(o["flow_note"])}</p>'
            f'<div class="pixel-card retention-card"><h2>{e(o["retention_title"])}</h2><p>{e(o["retention"])}</p></div>'
            f'<div class="section-heading"><h2>{e(o["compare_title"])}</h2></div>'
            f'<div class="comparison-scroll"><table class="comparison-table"><thead><tr>{headings}</tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="guide-link-row" id="full-guide"><a href="{e(article_href)}">{e(fit["long_label"])} ↗</a><span>{e(fit["long_note"])}</span></p></section>')


def home(locale: str, t: dict, p: dict, fit: dict, article_href: str) -> str:
    files = "".join(f'<li>{e(item)}</li>' for item in t["panel_files"])
    units = "".join(f'<span>{e(item)}</span>' for item in t["panel_units"])
    cards = "".join(link_card(locale, key, p, i) for i, key in enumerate(("how", "domains", "cases"), 1))
    return (f'<section class="hero wrap"><div class="hero-copy"><span class="eyebrow">✦ {e(t["hero_tag"])}</span>'
            f'<h1>{e(" ".join(t["hero_lines"]))}</h1><p class="hero-lead">{e(t["hero_lead"])}</p>'
            f'<div class="hero-actions">{link(locale, "start", t["hero_primary"], "button primary")}'
            f'{link(locale, "cases", t["hero_secondary"], "button secondary")}</div>'
            f'<p class="scope-note">{e(p["scope_note"])}</p></div>'
            f'<div class="terminal"><div class="terminal-top"><span>QIMING / WORKSPACE</span><span>● READY</span></div>'
            f'<div class="terminal-body"><div class="terminal-block"><small>01 / {e(t["panel_source"])}</small><ul>{files}</ul></div>'
            f'<div class="terminal-transfer">↓ {e(t["panel_arrow"])}</div>'
            f'<div class="terminal-block green"><small>02 / {e(t["panel_instance"])}</small><div class="unit-grid">{units}</div></div>'
            f'</div><div class="terminal-foot">PROJECT-LOCAL · Q/01</div></div></section>'
            f'<section class="statement"><div class="wrap"><span>※</span><p>{e(t["statement"])}</p></div></section>'
            f'{before_after(locale)}'
            f'{fit_panel(fit, article_href)}'
            f'<section class="page-section wrap"><div class="section-heading"><span class="eyebrow">EXPLORE / 03</span>'
            f'<h2>{e(p["section_more"])}</h2></div><div class="card-grid">{cards}</div></section>')


def start(locale: str, t: dict, p: dict, repo_url: str | None) -> str:
    steps = "".join(f'<article class="pixel-card step-card"><span class="pixel-index">{e(item["number"])}</span>'
                    f'<h2>{e(item["title"])}</h2><p>{e(item["body"])}</p></article>' for item in t["beginner_steps"])
    o = onboarding(locale)
    init_command = 'python3 .agents/skills/qiming/scripts/qiming.py init --root . --hosts auto'
    slug = repo_slug(repo_url)
    if slug:
        command = f"npx skills add {slug} --skill qiming"
        prompt = t["install_agent_template"].replace("{repo_url}", repo_url)
        install = (f'<div class="command-row"><code>{e(command)}</code>{copy_button(command, t)}</div>'
                   f'<div class="prompt-box"><strong>{e(t["install_prompt"])}</strong><p>{e(prompt)}</p>'
                   f'{copy_button(prompt, t)}</div><a class="source-link" href="{e(repo_url)}" rel="noopener noreferrer">'
                   f'{e(t["install_source"])} ↗</a>')
    else:
        install = f'<p class="pending">{e(t["install_pending"])}</p>'
    return (f'<section class="page-section wrap"><div class="steps-grid">{steps}</div>'
            f'<div class="section-heading"><span class="eyebrow">INSTALL / 01</span><h2>{e(t["install_title"])}</h2>'
            f'<p>{e(t["install_intro"])}</p></div><div class="install-panel"><div class="terminal-top">QIMING / INSTALL</div>'
            f'{install}<div class="prompt-box"><strong>{e(t["install_after"])}</strong><p>{e(t["install_adopt"])}</p>'
            f'{copy_button(t["install_adopt"], t)}</div><p class="install-note">{e(t["install_note"])}</p></div>'
            f'<div class="pixel-card init-panel"><h2>{e(o["init_title"])}</h2><div class="command-row"><code>{e(init_command)}</code>{copy_button(init_command,t)}</div><p>{e(o["init_note"])}</p></div>'
            f'<div class="pixel-card init-panel"><h2>{e(o["upgrade_title"])}</h2><p>{e(o["upgrade_note"])}</p></div>'
            f'<p class="scope-note">{e(p["scope_note"])}</p></section>')


def how(locale: str, t: dict, fit: dict, article_href: str) -> str:
    steps = "".join(f'<article class="pixel-card step-card"><span class="pixel-index">{e(item["number"])}</span>'
                    f'<h2>{e(item["title"])}</h2><p>{e(item["body"])}</p></article>' for item in t["methods"])
    chips = "".join(f'<span>{e(item)}</span>' for item in t["member_chips"])
    return (f'<section class="page-section wrap"><div class="steps-grid">{steps}</div>'
            f'<div class="member-panel"><div class="member-icon">Q+</div><div><span class="eyebrow">{e(t["member_label"])}</span>'
            f'<h2>{e(t["member_title"])}</h2><p>{e(t["member_body"])}</p><div class="chips">{chips}</div></div></div></section>'
            f'{before_after(locale)}{working_details(locale, article_href, fit)}')


def articles_index(locale: str, items: list[dict]) -> str:
    cards = []
    for index, item in enumerate(items, 1):
        available_locale = locale if locale in item["source"] else item["default_locale"]
        href = article_route(available_locale, item["slug"])
        cards.append(f'<article class="pixel-card article-card"><div class="case-top">'
                     f'<span class="article-number">{index:02d} / {len(items):02d}</span>'
                     f'<time datetime="{e(item["published"])}">{e(item["published"])}</time>'
                     f'<span>{e(item["availability"][locale])}</span></div>'
                     f'<h2>{e(item["title"][locale])}</h2><p>{e(item["summary"][locale])}</p>'
                     f'<a href="{e(href)}" hreflang="{available_locale}">{e(item["read_label"][locale])} ↗</a></article>')
    layout = "article-list single" if len(items) == 1 else "article-list"
    return f'<section class="page-section wrap"><div class="{layout}">{"".join(cards)}</div></section>'


def domains(t: dict) -> str:
    cards = "".join(f'<article class="pixel-card domain-card"><span class="eyebrow">{e(item["category"])}</span>'
                    f'<h2>{e(item["title"])}</h2><div class="quote"><b>{e(t["example_prompt"])}</b><p>{e(item["prompt"])}</p></div>'
                    f'<div class="result"><b>{e(t["example_result"])}</b><p>{e(item["result"])}</p></div>'
                    f'{copy_button(item["prompt"], t)}</article>' for item in t["examples"])
    return f'<section class="page-section wrap"><div class="domain-grid">{cards}</div></section>'


def cases(t: dict, p: dict) -> str:
    cards = []
    for i, item in enumerate([*t["real_cases"], p["self_case"]]):
        facts = "".join(f'<div class="case-fact"><b>{e(t["real_field_labels"][j]) if j < len(t["real_field_labels"]) else ""}</b>'
                        f'<p>{e(fact)}</p></div>' for j, fact in enumerate(item["facts"]))
        case_id = ' id="real-case-self"' if i == 2 else ""
        cards.append(f'<article class="pixel-card case-card"{case_id}><div class="case-top"><span>{e(item["category"])}</span>'
                     f'<span>{e(item["status"])}</span></div><h2>{e(item["title"])}</h2>{facts}'
                     f'<div class="prompt-box"><b>{e(t["real_prompt_label"])}</b><p>{e(item["prompt"])}</p>'
                     f'{copy_button(item["prompt"], t)}</div></article>')
    return f'<section class="page-section wrap"><div class="cases-grid">{"".join(cards)}</div></section>'


def prompts(t: dict) -> str:
    rows = "".join(f'<article class="prompt-row"><div><span class="pixel-index">0{i}</span><h2>{e(item["title"])}</h2></div>'
                   f'<p>{e(item["body"])}</p>{copy_button(item["body"], t)}</article>'
                   for i, item in enumerate(t["prompts"], 1))
    return f'<section class="page-section wrap"><div class="prompt-list">{rows}</div></section>'


def feedback(p: dict) -> str:
    f = p["feedback"]
    reports = [p[key] for key in ("legacy_feedback", "followup_feedback") if p.get(key)]
    report = "".join(f'<section class="page-section wrap"><article class="pixel-card feedback-card">'
                     f'<h2>{e(item["credit"])}</h2><p>{e(item["body"])}</p></article></section>' for item in reports)
    cards = "".join(f'<article class="pixel-card feedback-card"><span class="pixel-index">0{i}</span>'
                    f'<h2>{e(f[key + "_title"])}</h2><p>{e(f[key])}</p></article>'
                    for i, key in enumerate(("worked", "friction", "boundary"), 1))
    return (f'<section class="page-section wrap"><div class="source-banner"><span class="eyebrow">{e(p["evidence"])}</span>'
            f'<p>{e(f["credit"])}</p></div><div class="steps-grid">{cards}</div></section>' + report)


def story(t: dict) -> str:
    paragraphs = "".join(f'<p>{e(item)}</p>' for item in t["story_paragraphs"])
    return f'<section class="page-section wrap story-layout"><div class="story-mark" aria-hidden="true">Q<span>✦</span></div><div class="story-prose">{paragraphs}</div></section>'


def updates(t: dict) -> str:
    rows = "".join(f'<article class="update-row"><time datetime="{e(item["date"].replace(".", "-"))}">{e(item["date"])}</time>'
                   f'<div><h2>{e(item["title"])}</h2><p>{e(item["body"])}</p></div></article>' for item in t["changes"])
    return f'<section class="page-section wrap"><div class="updates-list">{rows}</div></section>'


def faq(t: dict) -> str:
    cards = "".join(f'<article class="pixel-card faq-card"><h2>{e(item["question"])}</h2><p>{e(item["answer"])}</p></article>'
                    for item in t["faq_items"])
    return f'<section class="page-section wrap"><div class="faq-grid">{cards}</div></section>'


def more(locale: str, p: dict) -> str:
    cards = "".join(link_card(locale, key, p, i) for i, key in enumerate(MORE_NAV, 1))
    return f'<section class="page-section wrap"><div class="card-grid">{cards}</div></section>'


def page_body(locale: str, page: str, t: dict, p: dict, fit: dict, repo_url: str | None,
              articles: list[dict]) -> str:
    featured_href = article_route(articles[0]["default_locale"], articles[0]["slug"])
    if page == "home":
        return home(locale, t, p, fit, featured_href)
    intro_class = "page-hero wrap article-index-hero" if page == "articles" else "page-hero wrap"
    intro = (f'<section class="{intro_class}"><span class="eyebrow">QIMING / {e(page.upper())}</span>'
             f'<h1>{e(p["labels"][page])}</h1><p>{e(p["lead"][page])}</p></section>')
    contents = {"start": lambda: start(locale, t, p, repo_url), "how": lambda: how(locale, t, fit, featured_href),
                "domains": lambda: domains(t), "cases": lambda: cases(t, p), "prompts": lambda: prompts(t),
                "feedback": lambda: feedback(p), "story": lambda: story(t), "updates": lambda: updates(t),
                "faq": lambda: faq(t), "more": lambda: more(locale, p),
                "articles": lambda: articles_index(locale, articles)}
    return intro + contents[page]()


def render(locale: str, t: dict, repo_url: str | None, site_url: str, page: str = "home", p: dict | None = None,
           fit: dict | None = None, articles: list[dict] | None = None, article: dict | None = None) -> str:
    validate_site_url(site_url)
    repo_slug(repo_url)
    if page not in PAGES:
        raise ValueError("unsupported page")
    if p is None:
        p = json.loads((HERE / "page_content.json").read_text(encoding="utf-8"))[locale]
    if fit is None:
        fit = json.loads((HERE / "fit_content.json").read_text(encoding="utf-8"))[locale]
    if articles is None:
        articles = article_catalog()
    if article is not None and locale not in article["source"]:
        raise ValueError("article translation is not available")
    canonical = site_url + (article_route(locale, article["slug"]) if article else route(locale, page))
    title = (f'{article["title"][locale]} | Qiming Skill' if article else
             t["title"] if page == "home" else f'{p["labels"][page]} | Qiming Skill')
    description = article["summary"][locale] if article else p["summary"][page]
    alternates = (article["source"] if article else LOCALES)
    alternate = "".join(f'<link rel="alternate" hreflang="{code}" href="{e(site_url + (article_route(code, article["slug"]) if article else route(code, page)))}">' for code in alternates)
    alternate += (f'<link rel="alternate" hreflang="x-default" href="{e(site_url + article_route(article["default_locale"], article["slug"]))}">'
                  if article else f'<link rel="alternate" hreflang="x-default" href="{e(site_url + route("zh-CN", page))}">')
    graph = [
        {"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical, "name": title,
         "description": description, "inLanguage": locale, "isPartOf": {"@id": site_url + "/#website"}},
        {"@type": "WebSite", "@id": site_url + "/#website", "url": site_url + "/", "name": "启明 Qiming", "inLanguage": list(LOCALES)},
    ]
    if repo_url:
        graph.append({"@type": "SoftwareSourceCode", "@id": site_url + "/#skill", "name": "Qiming Skill",
                      "description": t["description"], "url": site_url + "/", "codeRepository": repo_url,
                      "license": repo_url + "/blob/main/LICENSE", "programmingLanguage": ["Python", "Markdown"],
                      "isAccessibleForFree": True})
        graph[0]["about"] = {"@id": site_url + "/#skill"}
    if article:
        graph.append({"@type": "Article", "headline": article["title"][locale], "datePublished": article["published"],
                      "inLanguage": locale, "mainEntityOfPage": canonical})
    if page != "home":
        crumbs = [
            {"@type": "ListItem", "position": 1, "name": p["labels"]["home"], "item": site_url + route(locale)},
            {"@type": "ListItem", "position": 2, "name": p["labels"][page], "item": site_url + route(locale, page)}]
        if article:
            crumbs.append({"@type": "ListItem", "position": 3, "name": article["title"][locale], "item": canonical})
        else:
            crumbs[-1]["item"] = canonical
        graph.append({"@type": "BreadcrumbList", "itemListElement": crumbs})
    structured = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("<", "\\u003c")
    return f'''<!doctype html>
<html lang="{locale}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#10131b">
  <meta name="description" content="{e(description)}">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="{e(canonical)}">
  {alternate}
  <meta property="og:type" content="{'article' if article else 'website'}">
  <meta property="og:site_name" content="启明 Qiming">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(description)}">
  <meta property="og:url" content="{e(canonical)}">
  <meta property="og:locale" content="{OG_LOCALES[locale]}">
  <title>{e(title)}</title>
  <link rel="icon" href="/assets/favicon.ico" sizes="any">
  <link rel="icon" href="/assets/logo.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{asset_url('style.css')}">
  <script type="application/ld+json">{structured}</script>
  <script src="{asset_url('app.js')}" defer></script>
</head>
<body{f' class="article-page"' if article else ''}>
  <a class="skip-link" href="#main">{e(t['skip'])}</a>
  {header(locale, page, p)}
  <main id="main">{longform_article(article, locale, p['labels'], articles) if article else page_body(locale, page, t, p, fit, repo_url, articles)}</main>
  {footer(locale, p, t)}
</body>
</html>
'''


def sitemap(site_url: str, articles: list[dict] | None = None) -> str:
    if articles is None:
        articles = article_catalog()
    entries = []
    for page in PAGES:
        alternates = "".join(f'    <xhtml:link rel="alternate" hreflang="{code}" href="{xml_escape(site_url + route(code, page))}"/>\n' for code in LOCALES)
        alternates += f'    <xhtml:link rel="alternate" hreflang="x-default" href="{xml_escape(site_url + route("zh-CN", page))}"/>\n'
        for locale in LOCALES:
            entries.append(f'  <url>\n    <loc>{xml_escape(site_url + route(locale, page))}</loc>\n{alternates}  </url>\n')
    for item in articles:
        available = item["source"]
        article_alternates = "".join(f'    <xhtml:link rel="alternate" hreflang="{code}" href="{xml_escape(site_url + article_route(code, item["slug"]))}"/>\n' for code in available)
        article_alternates += f'    <xhtml:link rel="alternate" hreflang="x-default" href="{xml_escape(site_url + article_route(item["default_locale"], item["slug"]))}"/>\n'
        for locale in available:
            entries.append(f'  <url>\n    <loc>{xml_escape(site_url + article_route(locale, item["slug"]))}</loc>\n{article_alternates}  </url>\n')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "".join(entries) + '</urlset>\n')


def build(out: Path, repo_url: str | None, site_url: str) -> None:
    repo_slug(repo_url)
    validate_site_url(site_url)
    content = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
    pages = json.loads((HERE / "page_content.json").read_text(encoding="utf-8"))
    fits = json.loads((HERE / "fit_content.json").read_text(encoding="utf-8"))
    articles = article_catalog()
    if set(content) != set(LOCALES) or set(pages) != set(LOCALES) or set(fits) != set(LOCALES):
        raise ValueError("site content must contain exactly four supported locales")
    for locale in LOCALES:
        for page in PAGES:
            target = out / route(locale, page).lstrip("/")
            target.mkdir(parents=True, exist_ok=True)
            (target / "index.html").write_text(render(locale, content[locale], repo_url, site_url, page, pages[locale], fits[locale], articles), encoding="utf-8")
        for item in articles:
            if locale not in item["source"]:
                continue
            target = out / article_route(locale, item["slug"]).lstrip("/")
            target.mkdir(parents=True, exist_ok=True)
            (target / "index.html").write_text(render(locale, content[locale], repo_url, site_url, "articles", pages[locale], fits[locale], articles, item), encoding="utf-8")
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("style.css", "app.js", "logo.svg", "favicon.ico"):
        shutil.copyfile(HERE / "assets" / name, assets / name)
    (out / "release.json").write_text(json.dumps({"repo_url": repo_url, "site_url": site_url, "published": bool(repo_url)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nUser-agent: OAI-SearchBot\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n", encoding="utf-8")
    (out / "sitemap.xml").write_text(sitemap(site_url, articles), encoding="utf-8")


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

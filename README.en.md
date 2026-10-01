# Qiming Skill

[简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [English](README.en.md)

Qiming is a project-local AI management Skill for people starting with AI. Let an agent read the folder you already use, then keep work, knowledge, long-lived tools, and verification status in that project. A new agent, conversation, or computer can resume from the project's own entry.

Agent Dark源 and I grew Qiming from our real project management template. Its name also evokes the morning star. Every adopted project owns an independent instance and does not depend on the seed repository afterward.

## Start

Run this in the target project:

```sh
npx skills add cat9999aaa/qiming-skill --skill qiming
```

Then tell your agent:

> `$qiming` Adopt Qiming in this directory. Read the existing files and project rules first. Preserve the structure, then create this project's own entry and next step.

Installing the seed does not automatically adopt other directories. First use requires Python 3.11+. The pinned YAML/frontmatter dependency is in `skills/qiming/scripts/requirements.lock`.

## Scope and evidence

A “member” is a long-lived object you maintain, not a paid subscription. Scripts, Skills, programs, MCPs, and workflows can become members as work grows. For an urgent update, use the project instance's `qiming.py log` to append a timestamped event to an existing work record through the same checked transaction path. Account records hold secure-storage references, never passwords or keys.

Existing files and local conventions take priority. One OpenCode/GLM-5.3 field report supports the value of reading context, but the complete agent and OS matrix remains untested.

Website: [Get started](https://qiming.dashen.wang/en/start/) · [Use cases](https://qiming.dashen.wang/en/domains/) · [Real cases](https://qiming.dashen.wang/en/cases/) · [Feedback](https://qiming.dashen.wang/en/feedback/) · [Changelog](https://qiming.dashen.wang/en/updates/)

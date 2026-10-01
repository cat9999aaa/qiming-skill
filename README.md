# Qiming / 启明

Official website / 官网：https://qiming.dashen.wang/

Plain-language introduction and Omarchy local AI walkthrough (Simplified Chinese): https://qiming.dashen.wang/how/#full-guide

**Read in your language:** [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [English](README.en.md)

Qiming is a project-local AI management Skill for people starting with AI and people continuing complex work. It reads the working directory you choose, preserves existing files and conventions, and creates a self-contained instance for that project. Work, managed objects (“会员”), knowledge, and reusable tools remain yours.

我和我的 Agent Dark源在管理真实项目时，逐步沉淀出目录、规则、脚本与经验，启明从这套管理模板长出来。我用“启明”这个名字，也因为启明星会在天亮前指明方向。它希望让没用过 AI 的人从一个文件夹、一件事开始。首次接入后，每个项目持有自己的实例；后续工作不依赖安装种子的仓库。已有项目原地接续，原件和本地定制优先。

## Install the seed / 安装种子

Official source: https://github.com/cat9999aaa/qiming-skill. From the project where you want the seed available:

```sh
npx skills add cat9999aaa/qiming-skill --skill qiming
```

This installs a Skill through the [Skills CLI](https://github.com/vercel-labs/skills). It does not adopt or modify the project by itself. Choose the agent when the installer prompts you. First use needs Python 3.11+; YAML and frontmatter support use the pinned PyYAML version in `skills/qiming/scripts/requirements.lock`.

Then, in the target project directory, tell your agent:

> `$qiming` 在当前目录启用启明。先阅读已有文件和项目指令，保留原结构，建立本项目的独立实例与下一步。

To delegate installation to an agent:

> 请从 https://github.com/cat9999aaa/qiming-skill 安装 qiming Skill 到当前项目，先检查 Python 3.11+。保留已有文件和项目指令；安装后等我明确要求“在当前目录启用启明”再执行首次适配。

## What remains in your project / 项目里留下什么

- `.qiming/workspace.json` identifies this project's instance.
- The project-owned `qiming-user` Skill and short entry retain rules and current work.
- `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` point new sessions to the local context where supported.
- Members and work records are created as actual objects and tasks require them, not as an empty fixed tree.
- Account records retain secure credential references only. Never place passwords or keys in ordinary project documents.

“Member” means a user-owned object that needs long-term maintenance, not a paid plan. A project may gain scripts, Skills, programs, MCPs, workflows, and knowledge under its own ownership.

## Scope and verification / 范围与验证

The seed operates only when you explicitly ask to adopt or repair Qiming in a chosen project. Each adopted project has its own local instance. Installing the seed does not enable Qiming in other directories.

Project scope and continuity have automated checks and a targeted Codex trial. The complete cross-agent matrix and other OS/agent combinations have not been verified; do not infer universal compatibility from installation support.

The website source and four-language static output are under `site/`. See `site/README.md` for local preview and release configuration.

Explore the separate [getting started](https://qiming.dashen.wang/en/start/), [use cases](https://qiming.dashen.wang/en/domains/), [real cases](https://qiming.dashen.wang/en/cases/), [field feedback](https://qiming.dashen.wang/en/feedback/), and [changelog](https://qiming.dashen.wang/en/updates/) pages.

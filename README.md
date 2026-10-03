# Qiming / 启明

[![Tests](https://github.com/cat9999aaa/qiming-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/cat9999aaa/qiming-skill/actions/workflows/tests.yml) · Python 3.11+ · [v0.2.2](https://github.com/cat9999aaa/qiming-skill/releases/tag/v0.2.2)

Official website / 官网：https://qiming.dashen.wang/

Articles and the Omarchy local AI walkthrough (Simplified Chinese): https://qiming.dashen.wang/articles/organize-your-work/

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

## Start now / 现在接入

```sh
python3 .agents/skills/qiming/scripts/qiming.py init --root . --goal "完成当前项目的第一项任务" --hosts auto
```

默认 JSON 流程只需要 Python 3.11+；Windows 使用 `py -3`。安装路径不同时请替换。旧项目使用新安装包的 `upgrade_preview` / `upgrade`，本地规则、ID 与目录保持独立。

[完整入门](skills/qiming/references/quickstart.md) · [升级](skills/qiming/references/evolve.md) · [整改核验与边界](REMEDIATION.md) · [公开测试](CONTRIBUTING.md)

2026-10-01：Codex 和 Claude Code 的真实新会话接续抽查通过；Gemini CLI 需要登录，本次未验证；Cursor / OpenCode 完整行为矩阵待测。三系统 CI 结果见上方 Actions，不能从文件格式支持推断全部宿主兼容。

Operational guides: [English quickstart](skills/qiming/references/quickstart.en.md), [tools](skills/qiming/references/tools.en.md), [profile](skills/qiming/references/profile.en.md), [adaptation](skills/qiming/references/adapt.en.md). Other references and generated guidance remain primarily Chinese.

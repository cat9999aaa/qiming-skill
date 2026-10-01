# 从一个文件夹开始

需要能够读取项目文件、执行命令的 AI 助手，以及 Python 3.11+。普通网页聊天没有项目文件访问能力时，不能自动管理电脑目录。Linux/macOS 用 `python3`；Windows 用 `py -3`。默认 JSON 流程只用标准库，不需要 PyYAML。

## 新项目

在用户明确选定的项目根运行（将安装目录换成实际路径）：

```sh
python3 .agents/skills/qiming/scripts/qiming.py init --root . --goal "完成第一章修订" --hosts codex,claude
```

想先看影响：加 `--dry-run`，不会创建文件。`--preset dev` 增加事故记录集合；`--preset writing` 保持稿件原位置，用 JSON 管理工作，不猜测稿件目录。`--name` 记录用户给的项目名。默认 `--hosts auto` 建立通用 `.agents` 入口，并绑定当前项目已有的宿主目录；显式列表可绑定尚未出现的宿主目录。

同一个操作的完整 JSON 请求，可传给工具 `--stdin`：

```json
{"protocol":"qiming.tool/1","request_id":"init-1","op":"init","args":{"root":"/project","goal":"完成第一章修订","hosts":"codex,claude"}}
```

成功响应包含 `status: "ok"`、`result.workspace_id`、`result.instance_id`、`result.bound_hosts`、`changed`。ID、指纹和变更项取实际输出，不复制示例 ID。重复执行返回 `already_initialized: true`，无实际变化时 `changed: []`。

默认新增结构：

```text
AGENTS.md / CLAUDE.md / GEMINI.md  项目启动入口，保留用户原文
.qiming/
  workspace.json  profile.json   身份与现有目录的映射
  START.md  conventions.md       当前任务与稳定约定
  startup.md                    少量启动必读信息
  work/w-0001.json               给出 goal 时创建首任务
  knowledge/  members/          按实际成果写入记录
  qiming-user/                  本项目自己的规则与工具
```

## 记下来、找回来

```sh
python3 .qiming/qiming-user/scripts/qiming.py log .qiming/work/w-0001.json "第一章初稿完成；校对尚未运行" --workspace-manifest .qiming/workspace.json --intent-ref w-0001 --event-id chapter-draft-1
```

重复发送同一个 event-id 与事实不会重复追加。不同事实必须用新 ID。完整检索请求：

```json
{"protocol":"qiming.tool/1","request_id":"find-1","op":"search","workspace_manifest":"/project/.qiming/workspace.json","args":{"query":"第一章"}}
```

结果在 `result.items`，包含记录路径和指纹。`reindex` 重建可删除的 SQLite 索引；搜索以原记录为准。没有检索结果不表示任务完成。

## 已经接入过

再次 `init` 不会覆盖 profile、任务、ID 或本地规则。先读取 START.md，再从当前任务接续。旧实例升级请使用新安装包的 `upgrade_preview`，核对后再 `upgrade`；详见 [升级](evolve.md)。不要用新项目的默认 profile 覆盖旧项目。

Skills CLI 可能生成 `.agents/`、`.claude/`、`agent/`、`skills-lock.json` 等安装记录；这些不全由启明产生。种子 `qiming` 仅用于接入与升级；日常使用 `qiming-user`。保留种子便于升级，也可在检查归属后自行删除项目内种子。工具不会自动删除用户目录。

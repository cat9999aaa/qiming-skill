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
python3 .qiming/qiming-user/scripts/qiming.py log .qiming/work/w-0001.json "第一章初稿完成；校对尚未运行" --workspace-manifest .qiming/workspace.json --event-id chapter-draft-1
```

重复发送同一个 event-id 与事实不会重复追加。不同事实必须用新 ID。完整检索请求：

```json
{"protocol":"qiming.tool/1","request_id":"find-1","op":"search","workspace_manifest":"/project/.qiming/workspace.json","args":{"query":"第一章"}}
```

结果在 `result.items`，包含记录路径和指纹。`reindex` 重建可删除的 SQLite 索引；搜索以原记录为准。没有检索结果不表示任务完成。

## 已经接入过

再次 `init` 不会覆盖 profile、任务、ID 或本地规则。先读取 START.md，再从当前任务接续。旧实例升级请使用新安装包的 `upgrade_preview`，核对后再 `upgrade`；详见 [升级](evolve.md)。不要用新项目的默认 profile 覆盖旧项目。

Skills CLI 可能生成 `.agents/`、`.claude/`、`agent/`、`skills-lock.json` 等安装记录；这些不全由启明产生。种子 `qiming` 仅用于接入与升级；日常使用 `qiming-user`。保留种子便于升级，也可在检查归属后自行删除项目内种子。工具不会自动删除用户目录。

`log` 省略 `--intent-ref` 时，使用已选任务记录的 `id`；任务无 ID 时明确报错，也可显式指定。`init` 的 stdout 保持单条 JSON；stderr 显示项目目录、是否已接入、宿主绑定和下一步，方便人读与脚本解析同时使用。

## 控制根目录入口文件

默认 `--entry all` 管理 AGENTS.md、CLAUDE.md、GEMINI.md 的启明区块，保留区块外原文。可选 `--entry agents` 只管理 AGENTS.md；`--entry none` 不创建或修改这些根文件。先加 `--dry-run`，JSON 中 result.root_entry_files 和 root_file_actions 列出目标，stderr 也给人看的提示；dry-run 不写文件。

例如：`python3 .agents/skills/qiming/scripts/qiming.py init --root . --goal "整理研究记录" --entry none --dry-run`。确认实际影响后去掉 --dry-run。

入口选择保存于本项目 `workspace.json.extensions.entry_policy`。重复 init 与升级沿用原选择，命令参数不会重置已有项目。确需改变时，先审查并通过受控写入修改本地配置，再运行 refresh_context；已存在但停管的文件不删除，须人工审查旧入口是否仍被宿主读取。当前只提供 all/agents/none，不推断任意自定义路径的宿主自动发现能力。

`none` 下仍可使用目录中的工具，但宿主返回 manual-entry，不自动建立 Skill 绑定；每次显式读取 `.qiming/START.md`、conventions.md 和 qiming-user/SKILL.md。`agents` 下 Claude/Gemini 也可能需要人工配置；不要把文件存在当作已自动加载。

日志路径相对 work.root 登记根（默认项目根），必须包含 `.qiming/work/` 等集合目录前缀。English: [quickstart.en](quickstart.en.md)。

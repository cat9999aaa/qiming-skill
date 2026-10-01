# 宿主接续

用户实例是本项目的权威入口。种子仅在用户明确接入或修复时调用；Codex 种子设置 `allow_implicit_invocation: false`，项目实例保留自动调用。其他宿主不一定识别此策略，按该宿主支持的项目安装方式接入，不承诺全局种子在所有宿主都被同样隐藏。

路径角色：`.qiming/workspace.json` 定义项目身份和权威资料；`.qiming/qiming-user/` 保存本项目实例的规则与脚本；`.agents/skills/qiming-user`、`.claude/skills/qiming-user` 等是宿主发现用链接或可重建副本。调用工具始终传权威清单路径，不能从宿主副本位置猜测项目根。

`materialize` 在本项目根建立 `AGENTS.md`、`CLAUDE.md` 与 `GEMINI.md`。AGENTS 正文预载本项目范围、会员判断、衍生产物和收尾规则，以及本地 `startup.md` 摘要；Claude/Gemini 入口导入它。Markdown 普通链接不会自动把详细文件全部注入上下文。详细本地规则和目标记录在开始工作前按入口读取。

已有文件的手写内容保留；`refresh_context` 用 `.qiming/project-entrypoints.json` 核对生成区块指纹，仅更新未被用户改过的区块。摘要变更后刷新，不能只改来源文件就声称新会话已经读到更新。启动摘要上限为 12000 字节，超出时把细节留在原文；这只是本工具摘要上限，宿主的总上下文限制另行核对。

实例 `ready` 且 `validate` 通过后，用 `binding_preview` 看本项目内建议的 Skill 位置；它拒绝把项目实例绑定到其他根目录，并返回权威 `workspace_manifest`。项目根由清单的 `project_root` 定位，管理目录可以位于项目内部多层路径；旧默认布局兼容，无法唯一定位的旧自定义布局先补明确信息。建立链接或副本后运行 `binding_status`，检查摘要陈旧、区块改动、复制资源指纹和项目级 Codex `AGENTS.override.md` 的遮蔽；出现问题先解决实际入口，不把文件存在视为已预载。复制件可重建，权威资料与日志仍在原工作区；副本中的相对元数据不改变权威位置，工具请求使用启动指令或预览返回的原清单。

从项目根开启新会话验证。非 Git 子目录的宿主可能只读取当前目录指令，工具能发现父级清单不代表宿主会自动预载父级 AGENTS；应将任务工作目录设到项目根，或使用该宿主支持的项目根设置。不要为修复此项目修改全局人格。宿主全局覆盖、指令长度限制和用户自定义发现规则还需现场检查，`binding_status` 不是模型行为验收。

| 宿主 | 当前文档给出的项目 Skill 位置 | 来源 |
|---|---|---|
| Codex | `.agents/skills/<name>/SKILL.md` | [OpenAI Docs](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | `.claude/skills/<name>/SKILL.md` | [Claude Code Docs](https://code.claude.com/docs/en/skills) |
| Gemini CLI | `.gemini/skills/<name>/SKILL.md`，也识别 `.agents/skills` | [Gemini CLI Docs](https://geminicli.com/docs/cli/tutorials/skills-getting-started/) |
| Cursor | `.cursor/skills/<name>/SKILL.md`，也识别 `.agents/skills` | [Cursor Docs](https://prod.cursor.com/docs/skills) |
| OpenCode | `.opencode/skills/<name>/SKILL.md`，也识别 `.agents/skills` | [OpenCode Docs](https://opencode.ai/docs/skills) |


## 路径核对与验证边界

核对日期：2026-10-01。绑定结构的自动化测试不等于真实会话遵从。Python 3.11+；Linux/macOS 用 python3，Windows 用 py -3。复制绑定可用于无软链权限的环境。

| 宿主 | 项目 Skill 路径 | 当前验证 |
| --- | --- | --- |
| Codex | .agents/skills/qiming-user | 定向历史行为验证；本次新版本见发布验收 |
| Claude Code | .claude/skills/qiming-user | format-ok；完整行为矩阵 not-run |
| Gemini CLI | .gemini/skills/qiming-user | format-ok；完整行为矩阵 not-run |
| Cursor | .cursor/skills/qiming-user | 路径适配测试；真实行为 not-run |
| OpenCode | .opencode/skills/qiming-user | 单份现场反馈；完整行为矩阵 not-run |

官方资料：[Claude Code](https://code.claude.com/docs/en/skills)、[Gemini CLI](https://geminicli.com/docs/cli/using-agent-skills/)、[OpenCode](https://opencode.ai/docs/skills/)。具体版本可改变发现机制，始终看 binding_status 与真实新会话。

完整状态请求：

```json
{"protocol":"qiming.tool/1","request_id":"host-1","op":"binding_status","workspace_manifest":"/project/.qiming/workspace.json","args":{"host":"claude"}}
```

result.status 为 bound / bound-copy 才表示文件绑定就绪；instruction_bytes 表示 AGENTS.md 大小。它没有宣称模型一定遵从。

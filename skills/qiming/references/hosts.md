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

这些路径是文档层兼容信息。每个宿主还需实际验证格式识别、工具调用和目标行为三项。没有跑过的模型、版本、系统组合标为 `not-run`。只读宿主可接续与检索；写入、命令、凭据或调度能力必须按现场观测报告。GPT-6 Astra 的说明宜保持简短、按需展开，避免在入口堆叠重复流程；依据 [OpenAI 官方建议](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)。

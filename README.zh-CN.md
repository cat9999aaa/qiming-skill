# 启明 Skill

[简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [English](README.en.md)

启明是面向 AI 新手的项目本地管理 Skill。把已有文件夹交给 Agent，它先理解现场，再把任务、知识、长期维护的工具和验证状态留在项目中。换 Agent、换会话或换电脑时，从项目自己的入口接着做。

启明由我和 Agent Dark源在管理真实项目时沉淀而来。“启明”也取启明星的方向感。每个接入项目持有独立实例，后续不依赖安装种子的仓库。

## 开始

在目标项目运行：

```sh
npx skills add cat9999aaa/qiming-skill --skill qiming
```

然后对 Agent 说：

> `$qiming` 在当前目录启用启明。先看已有资料和项目规则，保留原结构，建立本项目的独立实例与下一步。

安装种子不会自动接管其他目录。首次运行需 Python 3.11+；YAML/frontmatter 依赖见 `skills/qiming/scripts/requirements.lock`。

## 工作与边界

“会员”是长期维护的独立对象，不是付费订阅。脚本、Skill、程序、MCP、流程等可以从项目工作中成长为会员。紧急时可用项目实例的 `qiming.py log` 向已有工作记录快速追加带时间的事件，仍经过事务和冲突检查。账户卡只保留安全存储的凭据引用。

已有项目结构和自定义优先保留。跨 Agent 读取有一份 OpenCode/GLM-5.3 现场报告，完整宿主矩阵仍待验证；不要把“安装成功”当作“所有场景通过”。

想先看懂它适合什么，可以读[完整介绍与 Omarchy 本地 AI 实战教程](https://qiming.dashen.wang/how/#full-guide)。

官网：[开始使用](https://qiming.dashen.wang/start/) · [领域](https://qiming.dashen.wang/domains/) · [真实案例](https://qiming.dashen.wang/cases/) · [用户反馈](https://qiming.dashen.wang/feedback/) · [更新日志](https://qiming.dashen.wang/updates/)

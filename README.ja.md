# 啓明 Qiming Skill

[![Tests](https://github.com/cat9999aaa/qiming-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/cat9999aaa/qiming-skill/actions/workflows/tests.yml) · Python 3.11+ · [v0.3.0](https://github.com/cat9999aaa/qiming-skill/releases/tag/v0.3.0)

[简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [English](README.en.md)

Qiming は、AI を使い始める人にも分かるプロジェクトローカルな管理 Skill です。既存のフォルダーを Agent が理解し、作業、知識、継続的に使うツール、検証状態をそのプロジェクトに残します。Agent や会話、PC が変わってもプロジェクトの入口から続けられます。

私と Agent Dark源が実際のプロジェクト管理で作ったテンプレートから育ちました。「啓明」には明けの明星という意味もあります。導入後の各プロジェクトは独立したインスタンスを持ち、元の種の保管場所に依存しません。

## 導入

対象プロジェクトで実行：

```sh
npx skills add cat9999aaa/qiming-skill --skill qiming
```

その後 Agent に伝えます：

> `$qiming` を今のディレクトリで有効にしてください。既存の資料と規則を読み、構造を残したまま、このプロジェクト専用の入口と次の作業を作ってください。

Skill のインストールだけでは、他のディレクトリを管理しません。初回は Python 3.11+ が必要です。YAML/frontmatter の依存関係は `skills/qiming/scripts/requirements.lock` を参照してください。

## 適用範囲

「会員」は有料プランではなく、継続的に保守する独立した対象です。スクリプト、Skill、プログラム、MCP、手順も対象になれます。緊急時はインスタンスの `qiming.py log` で既存の作業記録に時刻付きイベントを追加できます。認証情報は安全な保管先への参照だけを残します。

OpenCode/GLM-5.3 の現場報告は一件ありますが、全 Agent・OS の動作を証明するものではありません。

公式サイト：[始める](https://qiming.dashen.wang/ja/start/) · [活用分野](https://qiming.dashen.wang/ja/domains/) · [実例](https://qiming.dashen.wang/ja/cases/) · [記事](https://qiming.dashen.wang/ja/articles/) · [報告](https://qiming.dashen.wang/ja/feedback/) · [更新](https://qiming.dashen.wang/ja/updates/)

## 1 コマンドで導入、安全に更新

新規プロジェクトで実行します。再実行しても既存の規則や資料を上書きしません。Windows は py -3 を使用。標準 JSON は PyYAML 不要です。

```sh
python3 .agents/skills/qiming/scripts/qiming.py init --root . --hosts auto
```

[Quickstart](skills/qiming/references/quickstart.md) · [Profile](skills/qiming/references/profile.md) · [Upgrade](skills/qiming/references/evolve.md) · [Recovery](skills/qiming/references/recover.md) · [Audit remediation](REMEDIATION.md)

| Host | Project binding | Runtime check (2026-10-01) |
| --- | --- | --- |
| Codex | .agents/skills/qiming-user | Fresh-session continuity smoke passed |
| Claude Code | .claude/skills/qiming-user | Fresh-session continuity smoke passed |
| Gemini CLI | .gemini/skills/qiming-user | Not run: authentication required |
| Cursor | .cursor/skills/qiming-user | Format / binding tests only |
| OpenCode | .opencode/skills/qiming-user | One field report; full behavior retest pending |

The two smoke checks used synthetic project records. They are not the complete 34-scenario matrix. CI verifies automated tool tests on three operating systems; consult Actions for the actual run result.

Operational guides: [English quickstart](skills/qiming/references/quickstart.en.md), [tools](skills/qiming/references/tools.en.md), [profile](skills/qiming/references/profile.en.md), [adaptation](skills/qiming/references/adapt.en.md). Other references and generated guidance remain primarily Chinese.

Version/update checks: `python3 .qiming/qiming-user/scripts/qiming.py version --workspace-manifest .qiming/workspace.json` and `python3 .qiming/qiming-user/scripts/qiming.py check-update --workspace-manifest .qiming/workspace.json`. [Guide](skills/qiming/references/updates.en.md). This release uses the preview channel; checks never overwrite project rules.

## v0.3.0 の変更内容

- プロジェクトとパッケージのバージョンを分けて表示し、公式更新を照会します。
- 同じタスクの会話、プロジェクト、作業ディレクトリを確認して引き継ぎます。
- 入口の更新で未確認の範囲を明示し、独立した子プロジェクトの境界を守ります。
- 既存ルール・構成・タスク・会員 ID を保つ更新プレビューを使用します。

プレビュー版です。Windows の検証は未完了です。詳細と使い方、検証範囲は公式更新履歴をご覧ください。

[Changelog](https://qiming.dashen.wang/ja/updates/) · [v0.3.0](https://github.com/cat9999aaa/qiming-skill/releases/tag/v0.3.0)

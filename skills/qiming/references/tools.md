# 本地确定性工具

从本实例目录调用 `python3 scripts/qiming.py --stdin`，输入单个 UTF-8 JSON 请求，输出单个 `qiming.tool/1` JSON 响应。请求字段为 `protocol`、`request_id`、`op`、`workspace_manifest` 和 `args`；`inspect`、`bootstrap` 可不带清单。

常用顺序：`inspect → bootstrap → materialize → validate`；管理现有数据时先 `scan`，读写经 `plan → apply`，中断用 `reconcile`。知识用 `search` 和可重建的 `reindex`。`changed` 只列实际变动；`partial` 要查看覆盖范围与日志。

紧急现场给已有工作 JSON 追加一条事件，可从**项目实例的权威脚本**执行：

```sh
python3 .qiming/qiming-user/scripts/qiming.py log 'work/incident.json' '服务在 10:00 恢复；待重启复核' --workspace-manifest "$PWD/.qiming/workspace.json" --kind observation --intent-ref incident
```

`work/incident.json` 是相对 profile 中工作集合所用**根目录**的实际工作记录路径。短命令从 profile 读取该根，自动填写带时区的观察时间，返回同一 JSON 协议。可加 `--event-id` 固定事件身份，重试不会重复写入。支持 `observation`、`decision`、`action`、`handoff`。`log_event` 的 JSON args 是 `work_ref`（文件定位符）、`event`（`id/kind/summary/observed_at`）、`intent_ref`，可选 `expected_sha256`；它只修改映射的已有工作 JSON。冲突时重新读取现场，不能盲重试覆盖。

`scope_check` 的 args 为 `{"start_dir":"当前任务目录"}`，检查此任务是否属于清单对应的项目。它检查启用范围；授权操作的系统文件或远端资源不作为当前任务目录传入。`result.active` 为 false 时，不沿用该实例继续其他项目工作。

关键规则在控制目录的 `startup.md`（或清单 `startup_context`）维护，修改后调用 `refresh_context`，args 为 `{}`；只更新已跟踪的生成区块，手改区块返回冲突。`binding_preview` 的 args 为 `{"host":"codex","host_root":"本项目根"}`；`binding_status` 的 args 为 `{"host":"codex"}`。宿主名还可为 `claude`、`gemini`、`cursor`、`opencode`。

完整请求示例（路径按本实例实际位置填写）：

```json
{"protocol":"qiming.tool/1","request_id":"refresh-1","op":"refresh_context","workspace_manifest":"/project/.qiming/workspace.json","args":{}}
```

工具读取本地 profile 决定集合、字段、根和可写范围。调用方先依据当前任务确认授权。密码和密钥值只能交给专用凭据 provider；不放入普通 JSON 请求、日志或记录。

先记录实际宿主能力：文件读写、命令执行、受控写入、关键词搜索、SQLite、网络、服务连接、凭据 provider 与调度。只读能力可以完成理解和检索；没有可验证的受控写入时按单写入者工作，不宣称并发安全。`capability_report` 将格式识别、工具调用、行为通过分别记录，未运行保持 `not-run`。宿主路径与接续方式见[宿主](hosts.md)。

## 新手与维护入口（0.2）

- `init`：不需要 workspace_manifest；args 是 root、preset、name、goal、hosts、dry_run。完整命令与请求见 [quickstart](quickstart.md)。
- `bind`：args.host，建立本项目可发现入口；不能绑定到用户全局目录。
- `upgrade_preview` / `upgrade`：先比较再更新，见 [evolve](evolve.md)。
- `lock_status` / `lock_break`：只清理由已退出的本机进程留下的锁，见 [recover](recover.md)。
- `scan`：不给 roots 时观察映射集合的文件元数据；指定 roots 时按预算观察目录。不会读取任意业务正文。

状态：ok / ok_with_warnings 返回 0；error 返回 2；conflict 返回 3；partial 返回 4。partial 表示只完成一部分或检索覆盖缺失，不可当作全部通过。diagnostics.hint 提供下一步动作。

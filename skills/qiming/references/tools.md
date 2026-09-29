# 本地确定性工具

从本实例目录调用 `python3 scripts/qiming.py --stdin`，输入单个 UTF-8 JSON 请求，输出单个 `qiming.tool/1` JSON 响应。请求字段为 `protocol`、`request_id`、`op`、`workspace_manifest` 和 `args`；`inspect`、`bootstrap` 可不带清单。

常用顺序：`inspect → bootstrap → materialize → validate`；管理现有数据时先 `scan`，读写经 `plan → apply`，中断用 `reconcile`。知识用 `search` 和可重建的 `reindex`。`changed` 只列实际变动；`partial` 要查看覆盖范围与日志。

`scope_check` 的 args 为 `{"start_dir":"当前任务目录"}`，检查此任务是否属于清单对应的项目。它检查启用范围；授权操作的系统文件或远端资源不作为当前任务目录传入。`result.active` 为 false 时，不沿用该实例继续其他项目工作。

关键规则在控制目录的 `startup.md`（或清单 `startup_context`）维护，修改后调用 `refresh_context`，args 为 `{}`；只更新已跟踪的生成区块，手改区块返回冲突。`binding_preview` 的 args 为 `{"host":"codex","host_root":"本项目根"}`；`binding_status` 的 args 为 `{"host":"codex"}`。宿主名还可为 `claude`、`gemini`、`cursor`、`opencode`。

完整请求示例（路径按本实例实际位置填写）：

```json
{"protocol":"qiming.tool/1","request_id":"refresh-1","op":"refresh_context","workspace_manifest":"/project/.qiming/workspace.json","args":{}}
```

工具读取本地 profile 决定集合、字段、根和可写范围。调用方先依据当前任务确认授权。密码和密钥值只能交给专用凭据 provider；不放入普通 JSON 请求、日志或记录。

先记录实际宿主能力：文件读写、命令执行、受控写入、关键词搜索、SQLite、网络、服务连接、凭据 provider 与调度。只读能力可以完成理解和检索；没有可验证的受控写入时按单写入者工作，不宣称并发安全。`capability_report` 将格式识别、工具调用、行为通过分别记录，未运行保持 `not-run`。宿主路径与接续方式见[宿主](hosts.md)。

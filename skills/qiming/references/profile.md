# profile：让启明适配已有目录

`workspace.json` 的 roots 把短名字映射到目录；位置相对于该清单。`profile.json` 决定哪些文件属于工作、知识和会员。旧目录保持原样，只调整映射。先使用 `init --dry-run` 查看默认值；高级自定义才调用 bootstrap。

| 字段 | 含义与例子 |
| --- | --- |
| protocol | 固定 `qiming.profile/1` |
| collections | 集合名到配置的字典；例如 work |
| root | workspace roots 里已登记的名字，例如 project |
| directory | 相对根目录的位置，例如 `记录/任务`，不得包含 `..` |
| pattern | 相对集合目录的 glob；`**/*.json` 包括当前层和所有子目录 |
| codec | `json` 可结构化追加；`yaml`、`markdown-frontmatter` 为保真只读解析 |
| mapping | mappings 内存在的名称；把原文件字段转成统一视图 |
| exclude | 集合内排除模式，与 scope_rules.exclude 合并 |
| scope_rules.exclude | 相对登记根的排除规则；可用目录名或 glob |
| record_rules | 保留本地约定的扩展容器；没有自动业务规则引擎 |
| retrieval.max_candidates | 可选的检索候选上限；截断会报告 partial |
| retrieval.index_path | 可重建索引在控制目录内的位置，默认 index.sqlite |
| extensions | 用户扩展，工具保留 |

字段映射是 JSON Pointer，例如 `"name":{"source":"/title","default":"未命名","writable":false}`。`/` 写成 `~1`，`~` 写成 `~0`。`values` 可映射状态，如 `{"进行中":"open"}`。`writable` 是映射能力声明，不会赋予根目录写权限，也不是任意业务字段 setter。log 只追加标准 JSON work 的 events；普通 plan/apply 是指纹保护的字节写入。

完整通用配置见 [profile.example.json](../assets/contracts/profile.example.json)，三个预设共享 JSON 工作、知识、会员集合：general 通用；dev 另有 incidents；writing 保留正文原位置。已有 Markdown 稿件可另设只读集合：

```json
{"purpose":"drafts","root":"project","directory":"chapters","pattern":"**/*.md","codec":"markdown-frontmatter","mapping":"draft","exclude":["archive/**"]}
```

相应 `mappings.draft` 可为 `{"name":{"source":"/title","writable":false}}`。记录需要稳定 id，放在 frontmatter；无 frontmatter 的普通正文在检索时跳过，有 frontmatter 但损坏的记录报告错误。PyYAML 缺失时用当前解释器执行 `-m pip install PyYAML==6.0.3`；无需为了默认 JSON 流程安装它。

修改已有映射前使用 `plan_migration`，保留记录 ID 和正文。示例请求（新 profile 已审查并暂存）：

```json
{"protocol":"qiming.tool/1","request_id":"map-1","op":"plan_migration","workspace_manifest":"/project/.qiming/workspace.json","args":{"new_profile_ref":"/project/.qiming/new-profile.json","affected_collections":["work"],"intent_ref":"adapt-existing-records"}}
```

此调用只产生计划，不代表已迁移；检查实际结果后按工具协议 apply。完整操作字段见 [工具](tools.md)。

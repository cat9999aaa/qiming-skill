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

## 多层目录与分类

会员不要求平铺。已有 `members/00-foundation/`、`members/20-models/`、`members/99-archive/` 可以保持；设 directory 为 members、pattern 为 **/*.json（或既有 codec 对应扩展名）。这些名字只是示例，不自动创建空分类。

档案可保存 `category: "infra"`；原字段名不同则映射 `"category":{"source":"/group","writable":false}`。search 命中会携带 category，args.categories 可筛选。分类省略时返回 null，目录名不会被自动当作权限或归档状态；退役仍依据 lifecycle。依赖方向按 relations 单独记录。已有会员移动位置不得重建 ID；跨分类仍只有一份权威档案。

无 frontmatter 的 Markdown 会列入 coverage.skipped_files，reason 为 missing-frontmatter，并返回 partial。可先用宿主的只读文本搜索查正文；经用户确认再补稳定 ID 的 frontmatter 或建立显式 JSON 侧车。不要为了索引重写正文或用文件名冒充稳定会员 ID。当前没有隐式 filename 索引模式。

English: [profile.en](profile.en.md)。

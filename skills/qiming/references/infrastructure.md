# 基础设施与服务会员模板

按需扩展现有档案；不要求新建 infra 预设，不重写存量字段。独立维护的服务、模型部署、网关等可登记会员；其内部脚本归该会员，独立复用时再成为子会员。

```json
{
  "id": "使用本项目原有稳定ID",
  "type": "service",
  "name": "本地推理服务",
  "owner": "项目维护者",
  "scope": "workspace",
  "lifecycle": "maintained",
  "category": "infra",
  "boundary": {"listen": "127.0.0.1:8000", "exposure": "本机", "data_scope": "指定模型目录"},
  "version": {"value": "实际查询结果", "source": "经核验的发行来源或提交", "observed_at": "ISO-8601带时区"},
  "relations": [{"kind": "depends_on", "target": {"workspace_id": "依赖所在工作区ID", "id": "依赖会员ID"}}],
  "upgrade": {"method": "实际使用的升级方式", "preconditions": ["确认依赖兼容性与备份"], "source_task": "关联工作记录"},
  "rollback": {"steps": ["恢复已验证的旧版本和配置"], "backup_ref": "备份位置引用", "last_tested_at": null},
  "verification": [{"checked_at": null, "result": "not-run", "scope": "真实用户调用链", "evidence_refs": []}],
  "credential_ref": {"provider": "专用凭据存储", "id": "不包含凭据值的引用"}
}
```

上述是形状示例，不直接复制 ID 或把描述当成可执行命令。没有运行的检查用 null/not-run。依赖方向从本会员指向依赖对象；维护基础服务时另外查直接被依赖者，不能因目录叫 foundation 就推断已授权变更。verification 使用项目既有数组形状，最近一次 checked_at 表示实际验证时间；版本观测时间不替代功能验证。

排障先核对版本/来源、监听与暴露面、依赖、最后成功证据、最近变更及回退可用性。退役先查被依赖对象、数据保留责任和恢复入口，再由用户授权执行。详情见 [会员](members.md)、[安全](security.md)。

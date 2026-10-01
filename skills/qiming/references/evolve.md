# 演化本地管理规则

从当前目标、用户更正、重复错误、检索失败或复用反馈中找出实际要改的规则。先打开本地约定和 profile，确定最小影响范围，记录原因、旧规则指纹、预期改善、受影响记录、验证与回退入口。

影响开始工作时判断的职责、偏好或管理规则，应同步其在本地 `startup.md` 中的短摘要，注明权威来源后运行 `refresh_context`。详细事实保留在原记录；遇到手改生成区块，先比对并保留用户的真实规则。规则只作用于本项目，不自动推送到种子、其他项目或用户级配置。

文案小改只验证相关场景；涉及字段、分类或状态含义时先用 `plan_migration` 检查所有受影响记录，再用受控计划应用。迁移中断时按操作日志恢复，不能把新旧结构混用。旧 ID 与来源保持可追踪；无效规则可以撤回或删除。扩展能力不扩展用户授权。

`plan_migration` 需要候选 profile 的本地路径、受影响集合与本次工作引用。检查每条权威记录是否能保留 ID、字段语义和未知字段。计划把记录与 profile 纳入同一操作日志；执行前产生迁移标记，期间相关检索返回 `RECOVERY_REQUIRED`。完成或按指纹回退后移除标记。用户中途的新编辑产生冲突，先核对原件再决定下一步。

## 安全升级项目里的启明

从新安装包执行下面的请求，旧实例没有这些操作时也能升级：

```json
{"protocol":"qiming.tool/1","request_id":"upgrade-1","op":"upgrade_preview","workspace_manifest":"/project/.qiming/workspace.json","args":{"seed_dir":"/download/qiming"}}
```

`result.resources` 区分 unchanged、upgrade、local_modified、conflict、added、removed。检查后将完整 result 传回 upgrade 的 `args.preview`，同一结果的 plan_id 传入 `args.plan_id`。预览后任一相关文件改变会拒绝执行，必须重新预览。

未修改的运行资源通过 plan/apply 升级，用户修改的文件保留并列出。缺失的用户文件仍需修复；不以升级掩盖缺失。profile、任务、会员 ID 不在升级中改写，目录迁移另走 plan_migration。升级后检查 validate 和 refresh_context；有副本绑定时比较后重建，不能覆盖用户改过的副本。未提供新安装包时不联网猜测最新版本。

## 本地修改与版本追溯

实例属于本项目，可以修改。`validate` 对文件指纹变化返回 `ok_with_warnings` / `LOCAL_MODIFICATION`，保留修改并提示内容尚未经验证；文件缺失、身份错误和非法路径仍是错误。宿主副本必须与实际权威文件一致，陈旧副本仍报冲突。修改后需实际检查功能，不能把警告状态当作运行验证通过。

`seed_commit` 是发行时记录的源码提交，`seed_commit_kind: release-source` 表示它指向写入发行元数据之前的源码提交，不是包含自身哈希的最终提交。最终发布提交见 Release。`seed_package_sha256` 标识安装包实际字节；Git 换行设置或本地修改会改变它。通过 npx 安装即使没有 `.git` 也保留这些信息。未标记的开发包可没有 commit，但仍有包指纹，不虚构来源。

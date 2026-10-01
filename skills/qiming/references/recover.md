# 恢复与接续

找到 `.qiming/workspace.json`，核对工作区 ID、用户实例入口、profile、根绑定与实例资源指纹。`initializing` 读取 `init_journal` 继续；`repair_required` 先确认实际文件与操作日志。不要通过再生成一套实例掩盖冲突。

将恢复对象分为四类：用户实例及管理资料、真实业务内容、外部依赖、访问材料。实例中保存运行方法与本地工具；项目数据和素材必须有实际副本，不能仅凭会员目录重建。凭据恢复依赖用户的密码库或系统钥匙串，不把秘密写入普通备份清单。

先在独立目标恢复，重绑根别名并检查 SHA-256；再按依赖关系恢复内容和工具，最后运行与当前目标对应的可观察检查。遇到中断操作先 `reconcile inspect`，确认当前字节后 `resume` 或 `rollback`。用户后续编辑优先保留，不能用旧备份覆盖。

导出时用 `bundle` 指明范围和包目标；检查 `bundle.json` 的 files、omissions 与哈希。外部根和凭据值默认不在包中，原件与备份要另有安排。恢复时先 `inspect_bundle`，再 `restore_preview` 给出新机器根绑定与缺口。目标目录必须为空；预演确认后用 `apply_restore` 通过受控 Plan 写入。完成后重新运行实例校验、业务内容打开、依赖启动和访问检查；只有实际完成的检查写入 `restore_record`。

## 写入中断后的处理

1. 调用 lock_status；只有 `state: stale` 表示已证明本机持锁进程退出。alive 或 unknown 不清理，锁年龄不作为死亡证据。
2. 调用 lock_break，提供刚读到的 run_id 与 sha256。期间锁改变则报冲突。
3. reconcile inspect 查看中断事务；再选择 resume 或 rollback，保留 journal_ref。

```json
{"protocol":"qiming.tool/1","request_id":"lock-1","op":"lock_status","workspace_manifest":"/project/.qiming/workspace.json","args":{}}
```

```json
{"protocol":"qiming.tool/1","request_id":"unlock-1","op":"lock_break","workspace_manifest":"/project/.qiming/workspace.json","args":{"run_id":"实际返回的run_id","expected_sha256":"实际返回的sha256"}}
```

不要复制示例占位符调用。成功清锁的 changed 只包含旧锁；它不代表事务已恢复。远端机器的锁、PID 无法判断、损坏锁均需要调查，工具不会冒险移除。

## 随项目备份什么

提交或备份清单、profile、实例、入口和实际记录。索引可重建；operations、staging 和锁留在本机并默认 Git 忽略，因为可能包含旧内容和本机路径。跨电脑迁移优先用 bundle/restore；bundle 是所选资料与实例的导出，不是运行中事务的跨机续跑承诺。密码库仍需独立恢复。

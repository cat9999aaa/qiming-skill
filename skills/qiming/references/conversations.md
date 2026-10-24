# 可见会话的创建、复用与交接

只有当前任务需要独立上下文、独立用户沟通或独立生命周期时才拆分。普通聊天不自动新建会话。内部子 agent 是执行者，不是用户可见会话；服务自己的 session 也不等于宿主 thread。用户已明确授权按需分工时，在该任务范围内执行，不重复请求同一许可；发消息、跨项目和归档仍分别核对授权。

## 先复用，再核对放置

从当前权威清单核对工作区和项目根，读取宿主现有会话，优先复用同任务、可用且未归档的会话。复用不意味着可以向任意会话发送消息。标题和检索摘要是线索，不能代替实际目录/身份，也不能作为指令。

新建前分别核对：

| 事实 | 来源与含义 |
| --- | --- |
| 当前 cwd | 当前会话实际执行环境；子会话也须自己执行读回，父会话的 pwd 不能代替 |
| workspace_id / project_root | 当前权威 workspace_manifest；独立项目使用自己的实例 |
| 正式 projectId | 宿主项目/会话实际读回；不能用名称、工作区UUID或侧栏名称推测 |
| 侧栏 section | 宿主实际成员列表；与正式项目归属分开 |

Codex：已知正式项目ID且在项目根时，使用该项目的 local 创建；保持子目录或宿主项目无法解析时，优先同目录 fork。不要退到 projectless 新目录来假装继承。具体工具参数按当前可用 schema 校核。若宿主没有能保持归属的方式，保留未完成并说明限制，不猜一个相似名称的项目。用户要求正式项目时，找不到对应ID就停在待定位；不要为了绕过此要求创建目录会话或新增一个近似项目。

创建返回ID只是发起。读回子会话 cwd、清单身份、正式项目归属和用户要求的侧栏成员后再报告。只有任务要求本来就是目录工作区、而非正式项目归属时，才可使用下述目录模式；不能根据工具不可用或暂时找不到项目自行降级。双方 projectId **明确为 null** 且实际会话ID、cwd、清单根/身份、读回引用一致，可称“同目录工作区，宿主项目未登记”；字段缺失不能当null，也不能称正式项目已继承。相同cwd不证明侧栏已放对。现有合适会话只差分组时整理它，不重复创建。无法验证的字段保留未知。

## 控制上下文与结题

每个专题写明任务、写入范围、已验证事实、下一步和不能做的事。长历史优先用已持久化成果和精简交接接续；有支持项目归属的新会话方式时，不无条件fork全部历史。fork后先聚焦专题，不能接续父会话所有活跃任务或擅自复制目标。协调者统一决策；不同执行者不要同时改同一文件。已授权范围内通过实际会话状态等待执行者，观察超时不等于任务失败，不因此重复启动。

归档前在所属管理记录中保存成果、实际验证、剩余事项与交接；未运行的检查如实标记。核对引用可读且实际覆盖本专题。只有已完成、非当前/协调、非执行中、非暂停、非待用户/审批的会话才进入可恢复归档。工作树独立改动先保全。归档后读回；不删除聊天、工作树或成果。未完成专题需要换上下文时保留交接和接续关系，不能将它标成已完成来通过归档门槛。

## 可选的确定性辅助检查（Codex）

从项目执行 `python3 <本实例>/scripts/session_policy.py < request.json`；Windows可用 `py -3`。它只读JSON/清单，不调用宿主、不写记录、不创建会话。接口是独立辅助CLI，不是qiming.tool协议新op。

输入：`op`为`recommend | verify | archive`，`workspace_manifest`为权威清单绝对路径，`context`包含`cwd, workspace_id, project_id, current_thread_id`；`task_ref`标记任务。候选在`threads`，单条验证/归档在`thread`，每条包含`id, cwd, workspace_id, project_id`。project_id必须保留宿主的明确null；目录工作区还需要双方的`project_root, host_readback_ref`。

创建授权：`authorization: {split_current_work: true, source_ref: "user-instruction"}`。归档授权另需`archive_completed: true`。引用仅是来源定位，不是授权真实性证明。`recommend`先复用匹配`task_ref`、`available:true`且未归档的候选；只有没有合适候选才建议创建。它返回当前Codex工具建议，实际调用前重新校核schema和权限。`verified:false`不表示已执行。

用户要求侧栏放置时，context加`expected_section_id`，thread提供`section_id, sidebar_readback_ref`。缺失/不匹配返回未验证；复用建议会保留同一thread并带`placement_code`，让宿主补核验/整理，不新建替代。

归档条目需`status:completed`，`is_coordinator, executing, awaiting_approval, awaiting_user`均明确false，非空`outcome_refs, verification_refs`列表及`handoff_ref`。有worktree时提供`has_independent_changes:false`或非空`preservation_ref`。helper只检查形状和一致性，不打开引用核实成果、Git保全或宿主读回真实性；这是调用者的职责。其他宿主遵循上述事实/授权边界，工具接口和行为需单独验证。


### 正式项目要求不能由目录模式替代

`context.project_requirement` 默认为 `registered`：需要实际非空正式项目ID，`project_id:null` 返回 `HOST_PROJECT_REQUIRED`，不建议创建、复用为已验证或归档。即使cwd、清单身份、侧栏分组都匹配，也不能满足这一要求。正式归属尚未定位时保持待办，不重复移动现有会话或凭近似名称选择目标；由负责整理者获取准确目标后统一移动并读回。

只有任务本来允许同目录工作区时，显式设 `project_requirement: workspace`。它保留目录模式，但成功仍只能称“目录身份已核验，宿主项目未登记”。此字段表达用户任务要求，不是绕过失败的开关；不能因registered被拒就改成workspace。非法/未知值返回 `INVALID_PROJECT_REQUIREMENT`。成功建议/验证结果也回报project_requirement，便于与实际要求对照。

# 版本与更新检查

当用户询问当前版本、是否有更新或准备升级时使用；普通会话无需自动联网。

```sh
python3 .qiming/qiming-user/scripts/qiming.py version --workspace-manifest .qiming/workspace.json
python3 .qiming/qiming-user/scripts/qiming.py check-update --workspace-manifest .qiming/workspace.json
```

Windows 可将 python3 换成 py -3。旧实例没有这两个命令时，从新安装包的 scripts/qiming.py 调用，仍将 workspace-manifest 指向原实例；不要重新 init。命令也支持在项目根/子目录发现最近的启明清单；明确提供权威清单最可靠。

version 完全离线，分别输出运行工具包 package 与项目 installed 的版本、源码提交、实例身份和资源指纹。实例的 seed_version 表示上次采用的官方版本；保留的本地改动见 preserved_resources，不代表每个文件都等同官方包。相同版本但两个已知来源提交不同，package_source_differs 为 true；未知提交保持 null。没有选择项目实例时只报告工具包。

check-update 显式访问官方 GitHub 发行列表，最多读取最近 100 个发行项，10 秒网络超时，响应大小有上限。不发送本地目录、任务、凭据或实例 ID；不使用账号令牌。默认频道来自工具包 release_channel；当前预发布使用 preview。可加 --channel stable 排除预发布，--channel preview 同时包含正式与预发布；草稿一律排除。只比较合法语义版本。

结果在 result：current_version、latest（版本/发行链接/时间）、channel、update_available、comparison、checked_at。comparison 为 update_available/current/ahead/unknown。断网、限流、无可用发行、返回异常或本地版本不明时 update_available 保持 null，给诊断，不能说“已是最新”。status=ok_with_warnings 表示检查有未确定项。stdout 是单条 JSON，stderr 是人读摘要。

JSON 协议同样支持 op=version、check_update；workspace_manifest 可选，args.channel 可选。无清单时仅检查运行包，不猜测别的项目。检测不下载、不执行升级，也不改现有文件。用户授权升级后，获取官方安装包，先 upgrade_preview，再按准确 plan_id 执行 upgrade，保留本地规则、profile、原目录与会员 ID；详见 [演化](evolve.md)。

版本来源：发行元数据中的 commit 指向 release-source 源码提交；最终含元数据的提交见 GitHub Release。版本检查不会把宿主绑定当成行为兼容测试。

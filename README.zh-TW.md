# 啟明 Skill

[简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [English](README.en.md)

啟明是面向 AI 新手的專案本地管理 Skill。讓 Agent 從既有資料夾了解現況，再把任務、知識、長期工具與驗證狀態留在專案裡。換 Agent、換對話或換電腦時，都能從專案自己的入口接續。

啟明由我和 Agent Dark源在真實專案管理中累積而成；名字也有啟明星的意義。每個接入的專案都有獨立實例，之後不依賴安裝種子的倉庫。

## 開始

在目標專案執行：

```sh
npx skills add cat9999aaa/qiming-skill --skill qiming
```

再告訴 Agent：

> `$qiming` 在目前目錄啟用啟明。先閱讀既有資料和專案規則，保留原結構，建立本專案的獨立實例與下一步。

安裝種子不會自動接管其他目錄。首次執行需要 Python 3.11+；YAML/frontmatter 依賴見 `skills/qiming/scripts/requirements.lock`。

## 工作與範圍

「會員」是需要長期維護的獨立對象，不是付費訂閱。腳本、Skill、程式、MCP 和流程可從專案工作中發展為會員。緊急時可用實例的 `qiming.py log` 向既有工作紀錄追加帶時間的事件，仍經過交易與衝突檢查。帳戶卡只保存安全儲存的憑據參照。

既有結構與本地自訂優先保留。跨 Agent 讀取有一份 OpenCode/GLM-5.3 現場報告，完整宿主矩陣仍待驗證。

官網：[開始使用](https://qiming.dashen.wang/zh-TW/start/) · [領域](https://qiming.dashen.wang/zh-TW/domains/) · [案例](https://qiming.dashen.wang/zh-TW/cases/) · [文章](https://qiming.dashen.wang/zh-TW/articles/) · [回饋](https://qiming.dashen.wang/zh-TW/feedback/) · [更新](https://qiming.dashen.wang/zh-TW/updates/)

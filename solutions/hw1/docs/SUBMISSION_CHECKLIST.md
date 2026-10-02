# HW1 submission checklist

## 中文提交指南

提交地点：课程 **Brightspace 的 HW1 作业入口**。作业要求提交以下三项，不是只交代码。

| 要交什么 | 文件或链接 | 当前状态 |
| --- | --- | --- |
| GitHub 仓库链接 | https://github.com/VichyTong/CS593-ASE | 已推送；代码、运行说明和依赖配置在 `solutions/hw1/` |
| 简短演示视频 | `demo.mp4` | 已生成 1 分 44 秒的真实界面截图剪辑版；建议正式提交前按 `DEMO_SCRIPT.md` 录一遍实际操作，清楚展示五项功能 |
| 使用 coding agent 的反思报告 | `reflection.pdf`；可编辑原稿 `REFLECTION.md` | 草稿已写好，但需要你审阅、补充个人体验和真实聊天截图后再提交 |

### 按这个顺序完成

1. 阅读 `REFLECTION.md`，把体验与判断改成你本人认可的表述。报告要回答作业中的五个问题；反思占 HW1 的 40%。
2. 按 `SCREENSHOTS_TO_ADD.md` 截取这次聊天中的真实交互，重点展示你的指令、出现的问题、以及后续纠正。放进报告对应段落，再导出最终 PDF。工具无法截取 Codex 本身，所以这一步目前需要你提供截图；应用界面截图不能替代聊天截图。
3. 检查演示视频。当前 `demo.mp4` 是截图剪辑，不是连续操作录像。作业没有明确要求连续录屏，但录下真实的搜索、保存、上传、生成摘要、提问过程，会更直接地展示要求。已有逐步脚本，无需重新设计演示内容。
4. 打开 Brightspace 的 HW1 提交入口：提供仓库链接，上传最终演示视频与反思 PDF。仓库链接也保存在本目录的 `submission-links.txt` 中，便于复制；若入口只接受附件，可一并附上该文件。具体可用输入框和上传限制以课程页面为准。
5. 提交后确认 Brightspace 显示提交成功，并检查附件能够打开、仓库对评分人员可访问。这里尚未代你登录或提交 Brightspace。

截止时间：作业写的是 **10 月 10 日 23:59**，未注明时区，以课程页面为准。

提交代码不需要上传本地 `.env`、API Key、虚拟环境或运行数据库；这些已从 Git 排除。

---

## Application (60%)

- [x] Graphical frontend and backend.
- [x] External paper search with title, authors, publication year, abstract, and source link.
- [x] Save and browse papers in persistent SQLite storage.
- [x] PDF upload, text extraction, automatic metadata extraction, and metadata review.
- [x] LLM summary based on paper content.
- [x] Natural-language paper questions and source references.
- [x] GPT-6 Luna configuration, prompt cache, local result cache, and $5 spending ceiling.
- [x] Setup instructions, requirements, environment example, and deployment configuration.
- [x] Automated checks and actual live browser verification.

## Submission materials

- Repository: https://github.com/VichyTong/CS593-ASE
- Application: `solutions/hw1/`
- Video: `solutions/hw1/docs/demo.mp4` (captioned, edited walkthrough from real screenshots).
- Reflection: `solutions/hw1/docs/REFLECTION.md` and `reflection.pdf` (agent-assisted draft).

## Student actions before Brightspace submission

- [ ] Read and personalize the reflection so it accurately describes your own experience.
- [ ] Add the authentic coding-agent interaction screenshots listed in `SCREENSHOTS_TO_ADD.md`.
- [ ] Watch the video. If a continuous recording is preferred or required, record using `DEMO_SCRIPT.md`.
- [ ] Reproduce the key workflows and inspect the code so you can explain the application.
- [ ] Submit the repository link, video, and finalized reflection to Brightspace.

The assignment states a due date of **October 10, 11:59 PM**. Confirm the course's timezone in Brightspace. Public deployment is discussed in the overview but no separate deployed-URL item appears in the listed submission materials; this project includes local execution and deployment configuration, not a claimed hosted URL.

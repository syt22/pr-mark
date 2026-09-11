# pr-mark

[中文](#中文) | [English](#english)

## 中文

`pr-mark` 是一个用于 programming-language choice（编程语言选择）研究的轻量本地 Web 标注工具。它从 Markdown 文件导入 evidence URLs，将人工标注持久化到本地 SQLite，并支持 CSV 和 JSON 导出。

尽管项目名中包含 `pr`，数据源并不限于 Pull Request。记录可以来自 GitHub PR、Issue、Discussion、Commit、Repository、Release，也可以来自 Bugzilla、项目博客、公告、README、设计文档或其他 HTTP(S) 页面。

### 工作流程

```text
包含 evidence URLs 的 Markdown 文件
                ↓
        同步并识别数据源
                ↓
          浏览器人工标注
                ↓
        本地 SQLite 持久化
                ↓
          CSV / JSON 导出
```

本工具不会调用 GitHub API、抓取网页内容、调用 LLM，也不会自动判断某条记录是否属于 Good Data。

### 环境与安装

需要 Python 3.10 或更高版本以及现代浏览器。推荐使用 [uv](https://docs.astral.sh/uv/) 管理项目环境和锁定依赖；项目已包含 `pyproject.toml` 和 `uv.lock`。

安装 uv 后，在项目目录运行：

```bash
uv sync
```

uv 会自动创建并维护项目环境，不需要手动执行 `activate`。

如果在 WSL 中使用位于 Windows `/mnt/...` 文件系统上的同一个项目目录，建议使用独立环境名和复制模式，避免与 Windows 环境冲突及 hardlink 警告：

```bash
export UV_PROJECT_ENVIRONMENT=.venv-wsl
uv sync --link-mode=copy
```

`.venv-wsl/` 已加入 `.gitignore`，不会提交到 GitHub。

不使用 uv 时，仍可采用传统 `venv + pip`。

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS、Linux 或 WSL：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 启动

默认输入文件为项目上一级目录中的 `GoodData.md`：

```bash
uv run app.py
```

然后访问 <http://127.0.0.1:5000>。程序启动时会自动执行一次非破坏性同步。

WSL 与 Windows 共用项目目录时：

```bash
export UV_PROJECT_ENVIRONMENT=.venv-wsl
uv run --link-mode=copy app.py
```

指定其他 Markdown 文件：

```bash
uv run app.py --input ../GoodData.md
```

指定监听地址或端口：

```bash
uv run app.py --input ../GoodData.md --host 127.0.0.1 --port 5000
```

也可以把 `config.example.json` 复制为被 Git 忽略的 `config.json`，修改后运行：

```bash
uv run app.py --config config.json
```

命令行中的 `--input`、`--host` 和 `--port` 优先于配置文件中的对应值。

如果使用传统虚拟环境，将以上命令中的 `uv run app.py` 替换为 `python app.py`。

### URL 同步

点击顶部的 **Sync from GoodData.md**。程序会：

1. 提取 Markdown 链接和裸文本中的所有 HTTP(S) URL；
2. 清理 Markdown 标点，并按首次出现顺序对 canonical URL 去重；
3. 尽量识别 source type、GitHub repository 以及 number / ID；
4. 只插入数据库中尚不存在的 URL。

同步不会覆盖已有记录或人工标注。从 Markdown 删除 URL 也不会删除数据库记录。同步结果会显示找到、新增和已存在的 URL 数量。

### 标注界面

左侧可以浏览、搜索，并按 `scope` 和 `source_type` 筛选。右侧可以编辑：

页面顶部可以在中文和 English 之间切换；语言偏好保存在当前浏览器中，不会写入研究数据库。

- Source Type
- Target
- Status（数据库与导出字段名为 `project_status`）
- Candidates
- Choice
- Scope
- Evidence
- Rationale
- Other

修改会在短暂延迟后自动保存，界面显示 **Saving…**、**Saved** 或 **Save failed**。**Open Source** 会在新标签页打开原始证据。

### 数据与导出

默认数据库：

```text
data/annotations.db
```

点击 **Export CSV** 或 **Export JSON** 会生成并下载：

```text
exports/annotations.csv
exports/annotations.json
```

CSV 使用带 BOM 的 UTF-8，并正确转义多行字段。数据库、实际导出文件、虚拟环境、缓存、本地 `config.json` 和日志均被 `.gitignore` 排除，不应提交到 GitHub。`data/.gitkeep` 和 `exports/.gitkeep` 仅用于保留目录。

真实研究数据库不会自动备份，请自行保留备份副本。

### 测试

```bash
uv run python -m unittest discover -s tests -v
```

WSL 与 Windows 共用项目目录时，可运行：

```bash
export UV_PROJECT_ENVIRONMENT=.venv-wsl
uv run --link-mode=copy python -m unittest discover -s tests -v
```

测试覆盖 URL 提取、Markdown 链接、canonical URL 去重、GitHub 类型和 ID 识别、非 GitHub Blog 保留、同步不覆盖标注、空字段以及 CSV/JSON 导出。

### 当前 MVP 限制

- 没有身份认证、多用户或云数据库支持；除非明确了解风险，否则只应绑定 localhost。
- 不自动获取网页标题、正文、PR diff 或 rationale。
- 不使用 GitHub API 或 LLM。
- source type 依赖 URL 路径模式识别，但允许人工修正。
- 暂无记录删除、标注历史、撤销或多标签页并发协调。

### 许可证

[MIT](LICENSE)

---

## English

`pr-mark` is a lightweight local web annotation tool for programming-language choice research. It imports evidence URLs from a Markdown file, persists manual annotations in local SQLite, and exports the data as CSV or JSON.

Despite `pr` in the project name, sources are not limited to pull requests. Records may refer to GitHub PRs, issues, discussions, commits, repositories, and releases, as well as Bugzilla items, project blogs, announcements, READMEs, design documents, or other HTTP(S) pages.

### Workflow

```text
Markdown file containing evidence URLs
                  ↓
        Sync and classify sources
                  ↓
     Manual annotation in the browser
                  ↓
        Local SQLite persistence
                  ↓
           CSV / JSON export
```

The tool does not call the GitHub API, scrape source pages, invoke an LLM, or decide whether a record qualifies as Good Data.

### Requirements and installation

Python 3.10 or newer and a modern browser are required. [uv](https://docs.astral.sh/uv/) is recommended for environment and locked dependency management; the project includes both `pyproject.toml` and `uv.lock`.

After installing uv, run this from the project directory:

```bash
uv sync
```

uv creates and maintains the project environment automatically, so manual activation is unnecessary.

When using the same project directory from WSL on a Windows `/mnt/...` filesystem, use a separate environment name and copy mode to avoid conflicts with a Windows environment and hardlink warnings:

```bash
export UV_PROJECT_ENVIRONMENT=.venv-wsl
uv sync --link-mode=copy
```

`.venv-wsl/` is excluded by `.gitignore` and will not be committed to GitHub.

Without uv, the traditional `venv + pip` workflow remains supported.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS, Linux, or WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Start

The default input is `GoodData.md` in the project’s parent directory:

```bash
uv run app.py
```

Then open <http://127.0.0.1:5000>. The application performs a non-destructive sync at startup.

When WSL and Windows share the project directory:

```bash
export UV_PROJECT_ENVIRONMENT=.venv-wsl
uv run --link-mode=copy app.py
```

Select a different Markdown file:

```bash
uv run app.py --input ../GoodData.md
```

Choose a host or port:

```bash
uv run app.py --input ../GoodData.md --host 127.0.0.1 --port 5000
```

Alternatively, copy `config.example.json` to the Git-ignored `config.json`, edit it, and run:

```bash
uv run app.py --config config.json
```

Command-line `--input`, `--host`, and `--port` values take precedence over corresponding configuration values.

When using a traditional activated virtual environment, replace `uv run app.py` in these commands with `python app.py`.

### URL synchronization

Select **Sync from GoodData.md** in the top toolbar. The application:

1. extracts every HTTP(S) URL from Markdown links and bare text;
2. removes Markdown punctuation and deduplicates canonical URLs in first-seen order;
3. identifies the source type, GitHub repository, and number / ID where possible;
4. inserts only URLs that do not already exist in SQLite.

Synchronization never overwrites an existing record or manual annotation. Removing a URL from the Markdown input does not delete its database record. The result reports found, added, and existing URL counts.

### Annotation interface

The left panel supports browsing, searching, and filtering by `scope` and `source_type`. The right panel provides:

The page language can be switched between Chinese and English from the top toolbar. The preference is stored in the current browser and is not written to the research database.

- Source Type
- Target
- Status (stored and exported as `project_status`)
- Candidates
- Choice
- Scope
- Evidence
- Rationale
- Other

Changes are saved automatically after a short delay. The interface shows **Saving…**, **Saved**, or **Save failed**. **Open Source** opens the evidence page in a new tab.

### Data and export

The default database is:

```text
data/annotations.db
```

Select **Export CSV** or **Export JSON** to generate and download:

```text
exports/annotations.csv
exports/annotations.json
```

CSV uses UTF-8 with BOM and correctly quotes multiline fields. The database, generated exports, virtual environments, caches, local `config.json`, and logs are excluded by `.gitignore` and should not be committed to GitHub. `data/.gitkeep` and `exports/.gitkeep` only preserve the directories.

The real research database is not backed up automatically; keep a separate backup copy.

### Tests

```bash
uv run python -m unittest discover -s tests -v
```

When WSL and Windows share the project directory, run:

```bash
export UV_PROJECT_ENVIRONMENT=.venv-wsl
uv run --link-mode=copy python -m unittest discover -s tests -v
```

Tests cover URL extraction, Markdown links, canonical URL deduplication, GitHub classifications and identifiers, retention of non-GitHub blog URLs, synchronization without annotation overwrite, empty fields, and CSV/JSON exports.

### Current MVP limitations

- There is no authentication, multi-user support, or cloud database; bind only to localhost unless you understand the risks.
- Page titles, bodies, PR diffs, and rationales are not retrieved automatically.
- The tool does not use the GitHub API or an LLM.
- Source classification is URL-pattern based but can be corrected manually.
- There is no record deletion, annotation history, undo, or multi-tab concurrency coordination.

### License

[MIT](LICENSE)

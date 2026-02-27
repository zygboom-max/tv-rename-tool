# 📺 电视剧批量重命名工具

小爪子出品的剧集重命名神器 🐾

支持：**Alist** / **OpenList** / **百度网盘**

---

## ✨ 功能亮点

- 🎨 **美化输出** - 彩色日志、进度显示、表格预览
- 🛡️ **健壮异常处理** - 自动重试、详细错误信息、优雅降级
- 📊 **统计信息** - 扫描结果、成功/失败计数、无法识别文件列表
- ⏱️ **性能计时** - 显示操作耗时
- 🔍 **详细模式** - `-v` 参数显示调试信息
- 🎯 **智能解析** - 支持多种季集命名格式

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests colorama
```

### 2. 配置

编辑 `tv_rename.py` 中的配置区域，或复制示例配置：

```bash
cp config.example.json config.json
```

### 3. 运行

```bash
# 预览模式（推荐先预览）
python tv_rename.py

# 详细模式（显示调试信息）
python tv_rename.py -v

# 或直接执行（修改配置 dry_run: false）
```

---

## 📸 输出示例

```
╔══════════════════════════════════════════════════════════╗
║ 🐾 电视剧批量重命名工具                              小爪子出品  ║
╚══════════════════════════════════════════════════════════╝

✓ 配置已加载：config.json
✓ 已连接 Alist / OpenList
ℹ 测试连接...
✓ 连接正常
ℹ 命名模板：S{season:02d}E{episode:02d}

────────────────────────────────────────────────────────────
 扫描目录：/电视剧/权力的游戏
────────────────────────────────────────────────────────────
ℹ 找到 15 个文件

统计信息:
  可识别剧集：12
  需要重命名：10
  已符合/跳过：2
  无法识别：3

重命名预览:
原始文件名                                          → 新文件名
─────────────────────────────────────────────────────────────
Game.of.Thrones.S01E01.mkv              → S01E01.mkv
权力的游戏 第一季 第 02 集.mp4          → S01E02.mp4
...

⚠️  当前为预览模式，未实际重命名

是否执行重命名？[y/N]: y

开始执行重命名...

────────────────────────────────────────────────────────────
 执行重命名
────────────────────────────────────────────────────────────
[1/10] Game.of.Thrones.S01E01.mkv ✓
[2/10] 权力的游戏 第一季 第 02 集.mp4 ✓
...

重命名结果:
  成功：10
  失败：0

扫描 耗时：1.23 秒
重命名 耗时：3.45 秒

✨ 完成！
```

---

## ⚙️ 配置说明

### Alist / OpenList

1. 登录 Alist 管理后台
2. 获取 token（个人资料 → Token）
3. 配置 `base_url` 和 `token`

```python
ALIST_CONFIG = {
    "base_url": "http://localhost:5244",
    "token": "alist-xxxxxx",
    "root_path": "/电视剧/权力的游戏"
}
```

### 百度网盘

1. 访问 [百度网盘开放平台](https://pan.baidu.com/union/)
2. 创建应用获取 API Key
3. 通过 OAuth 获取 access_token

```python
BAIDU_CONFIG = {
    "access_token": "your-access-token",
    "root_path": "/电视剧/权力的游戏"
}
```

---

## 📝 命名模板

支持 Python 格式化字符串：

| 模板 | 输出示例 |
|------|----------|
| `S{season:02d}E{episode:02d}` | S01E01.mp4 |
| `Season {season} Episode {episode}` | Season 1 Episode 1.mp4 |
| `{season}x{episode:02d}` | 1x01.mp4 |
| `第{season}季 第{episode:02d}集` | 第 1 季 第 01 集.mp4 |

---

## 🔍 支持的文件名格式

自动识别以下格式：

- `S01E01`, `S1E1`
- `第 01 集`, `第 1 集`
- `EP01`, `E01`, `Ep01`
- `01 集`, `1 集`
- `Season 1 Episode 1`
- `1x01`, `01x01`

---

## 🎬 使用示例

### 示例 1：重命名《权力的游戏》

```python
STORAGE_TYPE = "alist"
ALIST_CONFIG = {
    "base_url": "http://192.168.1.100:5244",
    "token": "alist-abc123",
    "root_path": "/美剧/权力的游戏"
}
NAME_TEMPLATE = "S{season:02d}E{episode:02d}"
DRY_RUN = True  # 先预览
```

### 示例 2：百度网盘批量处理

```python
STORAGE_TYPE = "baidu"
BAIDU_CONFIG = {
    "access_token": "121.abc123...",
    "root_path": "/电视剧/甄嬛传"
}
NAME_TEMPLATE = "第{season}季 第{episode:02d}集"
DRY_RUN = False  # 直接执行
```

---

## ⚙️ 高级配置

### 配置文件选项

| 字段 | 类型 | 说明 |
|------|------|------|
| `storage_type` | string | `alist` 或 `baidu` |
| `dry_run` | boolean | `true` 预览模式，`false` 直接执行 |
| `verbose` | boolean | `true` 显示调试信息 |
| `name_template` | string | 命名模板 |

### 异常处理机制

- **自动重试**：网络请求失败自动重试 3 次，指数退避
- **超时保护**：请求超时 30 秒，避免无限等待
- **优雅降级**：colorama 缺失时自动使用 ANSI 转义码
- **详细错误**：失败时显示具体原因和失败文件列表
- **中断处理**：Ctrl+C 优雅退出，显示已完成的进度

---

## ⚠️ 注意事项

1. **先预览再执行**：`dry_run: true` 先看看效果
2. **备份重要数据**：虽然可逆，但小心为上
3. **token 安全**：不要提交到 git
4. **网络稳定**：批量操作需要稳定网络
5. **速率限制**：百度网盘有 API 调用限制，大量文件建议分批处理

---

## 🐛 常见问题

### Q: Alist 返回 401 错误
A: token 过期或错误，重新获取 token（Alist 管理后台 → 个人资料 → Token）

### Q: 百度网盘无法重命名
A: 检查 access_token 是否过期（有效期通常 30 天），需要重新授权获取

### Q: 文件名解析错误
A: 确保文件名包含季集信息，如 S01E01 或 第 01 集。使用 `-v` 参数查看详细解析日志

### Q: 连接超时
A: 检查网络连接，或增加 `request_timeout` 配置（需修改源码）

### Q: 部分文件重命名失败
A: 查看失败详情，常见原因：文件被占用、权限不足、名称冲突

### Q: 没有彩色输出
A: 安装 colorama：`pip install colorama`，程序会自动降级为 ANSI 模式

---

## 📦 依赖

- Python 3.7+
- requests

---

_Made with 🐾 by 小爪子_

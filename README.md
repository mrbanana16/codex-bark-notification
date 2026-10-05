# Codex Bark Notifications · v0.1

为 Codex 提供 Bark iOS 通知能力的本地 Plugin，通过 MCP 调用 Bark API。

## 功能

- 向一个或多个 iOS 设备发送通知，支持默认设备。
- 在 Codex 对话中添加、列出、删除设备和设置默认设备。
- 按明确授权，在任务完成、失败或需要人工介入时通知；默认不推送。
- Device Key 保存在仓库外的本地私有配置中，不进入 Git。

## 安装

需要 Python 3.10+ 和支持本地 Plugin 的 Codex CLI。执行：

```bash
git clone https://github.com/mrbanana16/codex-bark-notification.git
cd codex-bark-notification
python3 install.py
```

根目录 `install.py` 创建用户级 Python 环境，注册本地插件市场并启用 Plugin。随后重新加载 Codex，打开新会话。

macOS/Linux 配置默认位于 `~/.config/codex-bark-notification/devices.json`，支持 `XDG_CONFIG_HOME`；Windows 使用 `%APPDATA%`。

## 使用

1. 在 iOS 设备上安装 Bark App，并赋予联网和通知权限。
2. 在 Bark App 中复制 POST 使用示例命令，发给 Codex，并说明设备名称，例如：“请从这条 POST 命令中识别 Key，添加 Bark 设备 iPhone 并设为默认设备。”
3. Codex 会识别命令中的 Device Key，通过 MCP 保存到本地私有配置；不会在返回结果中重复显示 Key。不要把含真实 Key 的命令粘贴到仓库文件中。

配置完成后，可以这样使用：

- “添加一个 Bark 设备，名称为 iPhone。”（随后提供 Device Key）
- “列出我的 Bark 设备。”
- “把 iPhone 设置为默认设备。”
- “给 iPhone 发一条测试通知。”
- “全部测试完成后 Bark 通知我。”
- “部署失败时 Bark 通知 iPhone 和 iPad。”

请勿把 Device Key 放入代码、日志或提交。API 成功表示 Bark 已接受推送，手机实际展示取决于设备状态。

## 开发约定

根目录 README、AGENTS 和 Git 提交信息使用简体中文，其他开发文档、Skill、工具描述与错误信息使用英文。详细规则见 [AGENTS.md](AGENTS.md)。

## 待办

- 实现 Plugin GUI，用于管理 Bark 设备和 Device Key；当前仅通过 Codex 对话中的 MCP 工具管理。

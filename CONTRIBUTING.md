# 贡献指南 / Contributing Guide

感谢你对本项目的关注！

## 重要前提

本项目是一个**学习研究用的 Web 自动化技术示例**，所有贡献必须遵守以下原则：

1. 仅用于学习和研究目的
2. 不得添加任何可能用于商业抢购、代购的功能
3. 不得添加任何可能对目标平台造成恶意干扰的功能
4. 遵守相关法律法规和平台规则

## 如何贡献

### 报告 Bug

1. 在 Issues 中创建新 issue
2. 描述问题的复现步骤
3. 提供错误日志（位于 `logs/` 目录）
4. 说明你的运行环境（OS、Python 版本等）

### 提交代码

1. Fork 本仓库
2. 创建你的特性分支：`git checkout -b feature/amazing-feature`
3. 提交你的修改：`git commit -m 'Add some amazing feature'`
4. 推送到分支：`git push origin feature/amazing-feature`
5. 创建 Pull Request

### 代码规范

- Python 代码遵循 PEP 8 规范
- 所有公共函数和类必须有 docstring
- 新增功能需附带使用说明
- 不要提交敏感数据（Cookie、账号、密码等）

### Commit 信息格式

```
<类型>: <简短描述>

<详细说明（可选）>
```

类型包括：
- `feat`: 新功能
- `fix`: 修复 Bug
- `docs`: 文档更新
- `refactor`: 代码重构
- `style`: 代码格式调整
- `test`: 测试相关
- `chore`: 构建/工具链相关

## 行为准则

- 尊重所有参与者
- 接受建设性批评
- 专注于对社区最有利的事情
- 对他人表示同理心

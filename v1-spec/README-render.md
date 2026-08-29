# v1-spec — 渲染说明

本目录 Markdown 使用 GitHub Flavored Markdown（GFM）数学（KaTeX）语法，规则详见
`~/.config/opencode/skills/md-latex-rule/`（skill: md-latex-rule），要点：

- 行内公式用单美元号，块级公式用双美元号，块级必须独占整行并前后空行、零缩进。
- GitHub（网页文件预览）原生支持 KaTeX，无需任何插件。
- **本地预览**：VSCode 请安装 "Markdown+Math" 或 "Markdown Preview Enhanced"
  等扩展（默认 Markdown 预览不解析美元符号公式）。Typora 可用。
- 提交前运行校验（katex 全量解析 + GFM 结构规则）：

```bash
node ~/.config/opencode/skills/md-latex-rule/scripts/check_md_math.mjs <md 文件...>
```

- 公式内禁用：`\text{}` 内裸 `_`（写 `\_`）、`\text{}` 内 `\}`、Unicode 数学符号
  （`≤`/`≥` 用 `\le`/`\ge` 替代）、跨行行内公式。

## 示例（请照抄结构）

```markdown
行内：$x$、$V_\phi(s)$、$\approx$ 1B

块级（前空行 + 独占行 + 顶格 + 后空行）：

$$
\mathcal{L}(\theta) = -\mathbb{E}\log\pi_\theta(a\mid s)
$$
```

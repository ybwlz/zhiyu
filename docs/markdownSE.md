# 知屿 Markdown 语法说明

知屿的笔记支持一套丰富的 Markdown 语法，在 **Docs 阅览室 / 笔记阅读 / 编辑区** 三处渲染一致（个别能力有范围差异，已在文中标注）。以下按能力逐项说明，每条都给出「写法」与「效果」。

---

## 1. 基础语法

| 能力 | 写法 | 效果 |
| --- | --- | --- |
| 标题 | `# 一级`、`## 二级` … `###### 六级` | 各级标题 |
| 加粗 | `**加粗**` | **加粗** |
| 斜体 | `*斜体*` | *斜体* |
| 删除线 | `~~删除~~` | ~~删除~~ |
| 行内代码 | `` `code` `` | `code` |
| 链接 | `[文字](https://example.com)` | [文字](https://example.com) |
| 无序列表 | `- 项` / `* 项` | • 项 |
| 有序列表 | `1. 项` `2. 项` | 1. 项 2. 项 |
| 引用 | `> 内容` | 引用块 |
| 分割线 | `---` | 水平线 |
| 任务列表 | `- [ ] 待办` `- [x] 完成` | ☐ 待办 ☑ 完成 |

---

## 2. 表格（GitHub 风格）

**写法**

````text
| 列1 | 列2 | 列3 |
| --- | :---: | ---: |
| 左对齐 | 居中 | 右对齐 |
| a | b | c |
````

**效果**

| 列1 | 列2 | 列3 |
| --- | :---: | ---: |
| 左对齐 | 居中 | 右对齐 |
| a | b | c |

> 对齐方式：`:---` 左对齐、`:---:` 居中、`---:` 右对齐。

---

## 3. Emoji

**写法**：`:tada: :100: :heart:`

**效果**：🎉 💯 ❤️

> 完整表情列表见 [markdown-it-emoji](https://github.com/markdown-it/markdown-it-emoji/blob/master/lib/data/full.mjs)。

---

## 4. 代码块

### 4.1 语法高亮

**写法**

````text
```js
const greet = (name) => `Hello, ${name}!`
```
````

**效果**

```js
const greet = (name) => `Hello, ${name}!`
```

> 语言写在围栏后（`js` / `html` / `python` / `ts` / `css` …），支持 highlight.js 全部语言；代码块右上角有复制按钮，头部显示语言名。

### 4.2 行高亮

在围栏语言后加 `{行号}` 即可高亮指定行。

**写法**

````text
```js{2,5-6}
const a = 1
const b = 2      // ← 第 2 行高亮
const c = 3
const d = 4
const e = 5      // ← 第 5、6 行高亮
```
````

**效果**

```js{2,5-6}
const a = 1
const b = 2      // ← 第 2 行高亮
const c = 3
const d = 4
const e = 5      // ← 第 5、6 行高亮
```

> 支持：单行 `{4}`、多行 `{5-8}`、组合 `{1,4,6-8}`、混合 `{4,7-13,16,23-27,40}`。

### 4.3 行号

在围栏语言后加 `:line-numbers` 显示行号，`=N` 可自定义起始行号。

**写法**

````text
```python:line-numbers
def hello():
    print('hi')
```
````

**效果**

```python:line-numbers
def hello():
    print('hi')
```

**写法**

````text
```python:line-numbers=10
print('从第 10 行开始编号')
```
````

**效果**

```python:line-numbers=10
print('从第 10 行开始编号')
```

---

## 5. 代码组（tabs 切换）

把多个代码块放进 `::: code-group` 容器，每个代码块用 `[标题]` 命名，渲染为可切换的标签页。

**写法**

````text
::: code-group

```js [config.js]
const config = { name: 'demo' }
```

```ts [config.ts]
const config: Config = { name: 'demo' }
```

:::
````

**效果**

::: code-group

```js [config.js]
const config = { name: 'demo' }
```

```ts [config.ts]
const config: Config = { name: 'demo' }
```

:::

---

## 6. 自定义容器

### 6.1 基础类型

**写法**

````text
::: info
这是一条信息。
:::

::: tip
这是一条建议。
:::

::: warning
这是一个警告。
:::

::: danger
这是危险内容。
:::

::: details
这是可折叠的详细信息。
:::
````

**效果**

::: info
这是一条信息。
:::

::: tip
这是一条建议。
:::

::: warning
这是一个警告。
:::

::: danger
这是危险内容。
:::

::: details
这是可折叠的详细信息。
:::

### 6.2 自定义标题

在类型后直接跟标题文字。

**写法**

````text
::: danger STOP
危险区域，请勿继续！
:::

::: details 点我查看代码
```js
console.log('Hello, 知屿!')
```
:::
````

**效果**

::: danger STOP
危险区域，请勿继续！
:::

::: details 点我查看代码
```js
console.log('Hello, 知屿!')
```
:::

### 6.3 学习专用容器

笔记阅读页与编辑区额外支持：

````text
::: example
例题内容
:::

::: formula
公式推导内容
:::
````

---

## 7. GitHub 风格警报

**写法**

````text
> [!NOTE]
> 快速浏览时也不应忽略的重要信息。

> [!TIP]
> 有助于更顺利达成目标的建议。

> [!IMPORTANT]
> 对达成目标至关重要的信息。

> [!WARNING]
> 需要用户立即关注的关键内容。

> [!CAUTION]
> 行为可能带来的负面影响。
````

**效果**

> [!NOTE]
> 快速浏览时也不应忽略的重要信息。

> [!TIP]
> 有助于更顺利达成目标的建议。

> [!IMPORTANT]
> 对达成目标至关重要的信息。

> [!WARNING]
> 需要用户立即关注的关键内容。

> [!CAUTION]
> 行为可能带来的负面影响。

---

## 8. 数学公式（LaTeX）

行内公式用 `$...$`，块级公式用 `$$...$$`。

**写法**

````text
当 $a \ne 0$ 时，方程 $ax^2 + bx + c = 0$ 有两个解：

$$
x = {-b \pm \sqrt{b^2-4ac} \over 2a}
$$
````

**效果**

当 $a \ne 0$ 时，方程 $ax^2 + bx + c = 0$ 有两个解：

$$
x = {-b \pm \sqrt{b^2-4ac} \over 2a}
$$

> 支持 KaTeX/LaTeX 语法，也可在表格、列表中使用。

---

## 9. 图片与附件

**写法**

````text
![图片说明](/uploads/images/xxx.png)
````

**效果**：图片直接显示在正文中，支持缩放。

> - 上传笔记时，图片会自动上传并追加到正文末尾（文字在上、图片在下）。
> - 附件（PDF / Word / Excel / 压缩包等）会显示「📎 附件」下载按钮。

---

## 10. 目录（仅 Docs 阅览室）

在 Docs 阅览室中，`[[toc]]` 会渲染为文章目录（基于二、三级标题）。

````text
[[toc]]
````

> 笔记阅读页与编辑区暂不渲染 `[[toc]]`。

---

## 11. 批注（编辑区）

编辑区支持批注块（文字批注 / 手绘画布），保存为 `:::annotation` 容器。

````text
:::annotation
批注内容
:::
````

---

## 12. 知屿暂不支持的语法（VitePress 专属）

以下语法在知屿中**不会生效**，会按普通文本或普通代码显示：

- `<<< @/filepath` — 导入外部代码片段
- `<!--@include: @/xxx.md-->` — 包含其他 Markdown 文件
- `// [!code highlight]` / `// [!code focus]` / `// [!code --]` / `// [!code ++]` / `// [!code warning]` / `// [!code error]` — Shiki 专属代码行注释

> 代码行高亮请使用第 4.2 节的 `{行号}` 大括号语法。

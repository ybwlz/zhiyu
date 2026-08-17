/**
 * 文档块模型的兼容层。
 *
 * 正文 Markdown 只保存块的锚点，块的可编辑数据由独立记录保存。
 * 这样正文重渲染不会销毁手写输入状态，后续也可以把 note/image/drawing
 * 扩展成统一的块编辑器，而不用改变现有 Markdown 文件格式。
 */

export const BLOCK_TYPES = Object.freeze({
  NOTE: 'note',
  DRAWING: 'drawing',
  IMAGE: 'image',
})

const ANCHOR_RE = /:::annotation\s+([^\s]+)\s*\n?([\s\S]*?)\n?:::/g

export function normalizeBlock(record = {}) {
  const kind = record.kind === BLOCK_TYPES.DRAWING
    ? BLOCK_TYPES.DRAWING
    : record.kind === BLOCK_TYPES.IMAGE
      ? BLOCK_TYPES.IMAGE
      : BLOCK_TYPES.NOTE

  const block = {
    id: String(record.id ?? record.block_id ?? ''),
    kind,
    noteText: String(record.note_text ?? record.noteText ?? ''),
    strokes: Array.isArray(record.strokes) ? record.strokes : [],
    canvasW: Number(record.canvas_w ?? record.canvasW ?? 0) || 0,
    canvasH: Number(record.canvas_h ?? record.canvasH ?? 0) || 0,
    imagePath: String(record.img_path ?? record.imagePath ?? ''),
    anchor: String(record.anchor ?? ''),
  }
  // 兼容现有渲染器的 snake_case 字段，迁移期间两种命名都可读。
  block.note_text = block.noteText
  block.canvas_w = block.canvasW
  block.canvas_h = block.canvasH
  block.img_path = block.imagePath
  return block
}

/** 从 Markdown 中读取稳定的块锚点，不解析/改写正文其它内容。 */
export function readBlockAnchors(markdown = '') {
  const anchors = []
  let match
  ANCHOR_RE.lastIndex = 0
  while ((match = ANCHOR_RE.exec(String(markdown)))) {
    anchors.push({
      id: String(match[1]),
      offset: match.index,
      end: ANCHOR_RE.lastIndex,
      legacyContent: match[2] || '',
    })
  }
  return anchors
}

/** 在保存时只生成块锚点，不把文字/手绘重新序列化进正文。 */
export function serializeBlockAnchor(id) {
  const safeId = String(id || '').trim()
  return safeId ? `\n\n:::annotation ${safeId}\n:::\n\n` : ''
}

export function isDocumentBlockElement(node) {
  return !!(node && node.classList && node.classList.contains('ann-block'))
}

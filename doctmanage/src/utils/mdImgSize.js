// markdown 图片尺寸扩展：![alt](url "=宽x高") → 渲染 <img width height>
// 尺寸存放在 title 中（href 带空格会导致解析失败）
export default function mdImgSize(md) {
  const defaultImage = md.renderer.rules.image
  md.renderer.rules.image = (tokens, idx, options, env, self) => {
    const token = tokens[idx]
    const title = token.attrGet('title') || ''
    const m = title.match(/^=(\d+)(?:x(\d+))?$/)
    if (m) {
      token.attrSet('title', '')
      token.attrSet('width', m[1])
      if (m[2]) token.attrSet('height', m[2])
    }
    return defaultImage
      ? defaultImage(tokens, idx, options, env, self)
      : self.renderToken(tokens, idx, options)
  }
}

<template>
    <div class="upload-container">
      <!-- 左侧：表单区域 -->
      <div class="form-section">
        <el-form :model="form" ref="formRef" label-width="120px" status-icon>
          <!-- 主标题 -->
          <el-form-item class="form-item" label="主标题" prop="type" :rules="typeRules">
            <el-autocomplete
                v-model="form.type"
                placeholder="请输入主标题"
                :disabled="uploadLoading"
                :fetch-suggestions="querySearch"
            />
          </el-form-item>

          <!-- 文章标题 -->
          <el-form-item class="form-item" label="文章标题" prop="title" :rules="titleRules">
            <el-input class="input"  v-model="form.title" placeholder="请输入文章标题" :disabled="uploadLoading"/>
          </el-form-item>

          <!-- 文件上传 -->
          <el-form-item label="上传文件" prop="file" :rules="fileRules" :disabled="uploadLoading" >
            <template #label>
              <span class="required">上传文件</span>
            </template>
            <el-upload
                class="upload-demo"
                drag
                action=""
                :on-change="beforeUpload"
                :on-remove="handleRemove"
                :file-list="fileList"
                :limit="1"
                :accept="'.md'"
                :on-exceed="handleExceed"
            >
              <template #default>
                <div v-if="!form.file">
                  <i class="el-icon-upload"></i>
                  <div class="el-upload__text">
                    <span>拖拽文件或点击上传</span><br />
                    <span>仅限markdown文件</span>
                  </div>
                </div>
              </template>

            </el-upload>
          </el-form-item>

          <!-- 提交按钮 -->
          <el-form-item>
            <el-button
                type="primary"
                @click="submitForm"
                :disabled="uploadLoading"
            >
              {{ uploadLoading ? '提交中...' : '提交'}}
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 右侧：预览区域 -->
      <div class="preview-section" v-if="form.file && markdownContent">
        <el-tabs v-model="activeTab" type="border-card" class="preview-tabs">
          <el-tab-pane label="预览" name="preview">
            <div class="markdown-preview-wrapper">
              <div class="markdown-body preview-content" v-html="renderedMarkdown"></div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="源码" name="source">
            <el-input
                v-model="markdownContent"
                type="textarea"
                :rows="20"
                readonly
                class="markdown-source"
            />
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
</template>

<script setup>
import {ref, watch, computed} from 'vue';
import {ElMessage} from "element-plus";
import {useFileListStore} from "@/stores/fileList.js";
import {storeToRefs} from "pinia";
import api from "@/utils/api.js";
import MarkdownIt from 'markdown-it';
import anchor from 'markdown-it-anchor'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { full as emoji } from 'markdown-it-emoji'
import container from 'markdown-it-container'
import mathjax3 from 'markdown-it-mathjax3'
import alerts from 'markdown-it-github-alerts'
import toc from 'markdown-it-toc-done-right'

const slugify = (s) => {
  const text = String(s || '').replace(/<[^>]+>/g, '')
  return text.trim().toLowerCase().replace(/[^\w\u4e00-\u9fa5]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || 'section'
}

// 初始化 Markdown 渲染器
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang, ignoreIllegals: true }).value;
      } catch (__) {}
    }
    return ''; // 使用外部默认转义
  }
});

md.use(anchor, {
  slugify,
  permalink: anchor.permalink.linkInsideHeader({
    symbol: '#',
    placement: 'before',
    class: 'header-anchor',
    ariaHidden: true
  })
})

// --- 扩展 ---
md.use(emoji)
md.use(mathjax3)
md.use(alerts)
// 目录: [[toc]]
md.use(toc, {
  listType: 'ul',
  slugify
})

// 自定义容器 (VitePress 风格)
const createContainer = (klass, defaultTitle) => {
  return [container, klass, {
    render: function (tokens, idx) {
      const token = tokens[idx]
      const info = token.info.trim().slice(klass.length).trim()
      if (token.nesting === 1) {
        const title = info || defaultTitle
        return `<div class="${klass} custom-block"><p class="custom-block-title">${title}</p>\n`
      } else {
        return `</div>\n`
      }
    }
  }]
}

md.use(...createContainer('tip', 'TIP'))
md.use(...createContainer('info', 'INFO'))
md.use(...createContainer('warning', 'WARNING'))
md.use(...createContainer('danger', 'DANGER'))

// 详情折叠
md.use(container, 'details', {
  render: function (tokens, idx) {
    const token = tokens[idx]
    const info = token.info.trim().slice('details'.length).trim()
    if (token.nesting === 1) {
      return `<details class="custom-block details"><summary>${info || 'Details'}</summary>\n`
    } else {
      return `</details>\n`
    }
  }
})

// 代码组
md.use(container, 'code-group', {
  render: function (tokens, idx) {
    if (tokens[idx].nesting === 1) {
      return `<div class="code-group">\n`
    } else {
      return `</div>\n`
    }
  }
})

md.renderer.rules.fence = function (tokens, idx, options, env, self) {
  const token = tokens[idx];
  const info = token.info ? md.utils.unescapeAll(token.info).trim() : '';
  let langName = '';
  if (info) {
    langName = info.split(/\s+/g)[0];
  }
  
  const highlighted = options.highlight 
    ? options.highlight(token.content, langName) 
    : md.utils.escapeHtml(token.content);
    
  const languageClass = langName ? 'language-' + langName : '';
  const label = langName ? langName.toUpperCase() : '';
  
  return  `<div class="code-block-wrapper">` +
            `<div class="code-header">` +
              `<span class="code-lang">${label}</span>` +
              `<button class="copy-code-btn" data-code="${encodeURIComponent(token.content)}"></button>` +
            `</div>` +
            `<pre class="${languageClass}"><code class="${languageClass}">${highlighted}</code></pre>` +
          `</div>`;
};

const drawer = ref(false);
const form = ref({
  type: '数学公式',
  title: '',
  file: null
});
const formRef = ref(null);
const fileList = ref([]);
const markdownContent = ref('');
const activeTab = ref('preview');

// 标题必填校验规则
const titleRules = [
  { required: true, message: '请输入文章标题', trigger: 'blur' }
];

const typeRules = [
  { required: true, message: '请输入主标题', trigger: 'blur' }
]

// 文件上传的校验规则
const fileRules = [
  {
    validator: (rule, value, callback) => {
      if (fileList.value.length === 0) {
        callback(new Error('请上传一个文件'));
      } else {
        callback(); // 校验通过
      }
    },
    trigger: 'change',
  }
];

const querySearch = (queryString, cb) => {
  const suggestions = typesData.value;

  const results = queryString
      ? suggestions.filter(suggestion => suggestion.value.includes(queryString))
      : suggestions;
  cb(results);
};

// 上传前的检查
const beforeUpload = (file) => {
  // 获取文件扩展名
  const fileExtension = file.name.split('.').pop().toLowerCase();

  // 校验文件扩展名是否为 .md
  if (fileExtension !== 'md') {
    ElMessage.error('只能上传 .md 文件');
  } else {
    fileList.value = [file];
    form.value.file = file;
    
    // 读取文件内容用于预览
    const reader = new FileReader();
    reader.onload = (e) => {
      markdownContent.value = e.target.result;
    };
    reader.onerror = () => {
      ElMessage.error('文件读取失败');
    };
    reader.readAsText(file.raw);
  }
};

// 处理文件列表超过限制
const handleExceed = () => {
  ElMessage.error('只能上传一个文件');
};

// const getData = () => {
//   fileListStore.dataRefresh()
// }

// 移除文件时的回调
const handleRemove = (file, fileList) => {
  form.value.file = null; // 移除文件时清空
  markdownContent.value = ''; // 清空预览内容
};

watch(() => form.value.file, () => {
  if (form.value.file) {
    document.querySelector('.upload-demo .el-upload .el-upload-dragger').style.padding = '0';
    document.querySelector('.upload-demo .el-upload .el-upload-dragger').style.borderWidth = '0';
  } else {
    document.querySelector('.upload-demo .el-upload .el-upload-dragger').style.padding = '40px 10px';
    document.querySelector('.upload-demo .el-upload .el-upload-dragger').style.borderWidth = '1px';
  }
})

const fileListStore = useFileListStore()
const { fileListData, typesData } = storeToRefs(fileListStore)

let uploadLoading = ref(false)

// 渲染 Markdown 为 HTML
const renderedMarkdown = computed(() => {
  if (!markdownContent.value) return '';
  return md.render(markdownContent.value);
});

// 提交表单
const submitForm = () => {
  formRef.value.validate((valid) => {
    if (valid) {
      // 每次提交都创建新的 FormData，避免数据累积
      const formData = new FormData()
      uploadLoading.value = true

      formData.append('file', form.value.file.raw);
      formData.append('title', form.value.title);
      formData.append('type', form.value.type);
      
      // 这里可以执行文件上传或其他操作
      api.post('/docs', formData)
          .then(res => {
            fileListStore.fetchDocs()

            ElMessage.success('上传成功')
            form.value.file = null
            form.value.title = ''
            markdownContent.value = '' // 清空预览内容

            fileList.value = []
            drawer.value = false
          })
          .catch(err => {
            // 显示更详细的错误信息
            ElMessage.error('上传失败')
          })
          .finally(() => {
            uploadLoading.value = false
          })
    } else {
      console.log('表单验证失败');
      return false;
    }
  });
};
</script>

<style scoped>
/* 容器布局：左右分栏 */
.upload-container {
  display: flex;
  gap: 0;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  align-items: stretch;
}

/* 左侧表单区域 */
.form-section {
  flex: 0 0 500px;
  min-width: 500px;
  max-width: 500px;
  flex-shrink: 0;
  padding: 20px;
  border-right: 1px solid var(--border);
  overflow-y: auto;
}

/* 右侧预览区域 */
.preview-section {
  flex: 1;
  min-width: 400px;
  flex-shrink: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.upload-demo i {
  font-size: 50px;
  color: var(--brand-1);
}

.upload-demo .el-upload__text {
  font-size: 16px;
  color: var(--text2);
  white-space: normal;
}

.floating-ball {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background-color: var(--brand-1);
  color: var(--btn-text-contrast);
  border-radius: 50%;
  width: 50px;
  height: 50px;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  box-shadow: var(--shadow-1);
  font-size: 24px;
  z-index: 100;
}

.full-box {
  position: absolute;
  z-index: 101;
  background: var(--overlay-bg);
  width: 100vw;
  height: 100vh;
}

.right-box {
  position: absolute;
  z-index: 102;
  width: 50%;
  height: 100%;
  background: var(--bg);
  right: 0;
}

.close {
  display: none;
}

.form-item, .input {
  display: flex;
  flex: 1;

  max-width: 400px;
}

.required:before {
  color: var(--el-color-danger);
  content: "*";
  margin-right: 4px;
}

.required {
  line-height: 49px;
}

/* Markdown 预览样式 */
.preview-tabs {
  width: 100%;
  height: 100%; /* 填充预览区域 */
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.preview-tabs :deep(.el-tabs__header) {
  margin: 0;
  flex-shrink: 0;
  order: 0; /* 确保头部在顶部 */
}

.preview-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden; /* 内容区域作为可滚动面板的容器 */
  padding: 0;
  min-height: 0;
  position: relative;
  order: 1; /* 确保内容在头部下方 */
}

.preview-tabs :deep(.el-tab-pane) {
  /* 移除绝对定位以恢复正常流 */
  height: 100%;
  padding: 0;
  display: block; /* 从 flex 改为 block/默认 */
  overflow: hidden; /* 让子元素处理滚动 */
  width: 100%;
}

/* Markdown Preview Wrapper */
.markdown-preview-wrapper {
  width: 100%;
  height: 100%; /* 填充标签页 */
  overflow-y: auto; /* 内部滚动 */
  overflow-x: hidden;
  padding: 0; /* 让内部内容处理内边距 */
  box-sizing: border-box;
  background-color: var(--bg);
  /* border: 1px solid var(--border); 移除边框，因为标签页已经有边框了 */
  /* border-radius: 4px; */
}

.preview-content {
  max-width: 880px;
  margin: 0 auto;
  padding: 32px 100px 50px;
  box-sizing: border-box;
}

/* 响应式 padding，保持与 DocsLayout 一致 */
@media (max-width: 959px) {
  .preview-content {
    padding: 24px 24px;
  }
}

/* 移除 .markdown-preview 相关样式，使用全局 .markdown-body 样式 */

.markdown-source {
  width: 100%;
  max-width: 100%;
  height: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.markdown-source :deep(.el-textarea) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.markdown-source :deep(.el-textarea__inner) {
  flex: 1;
  width: 100%;
  max-width: 100%;
  padding: 20px;
  box-sizing: border-box;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  border: 1px solid var(--border);
  border-radius: 4px;
  resize: none;
  overflow-y: auto !important;
  overflow-x: hidden;
  overflow-wrap: break-word;
  word-wrap: break-word;
  min-height: 0;
}

/* 响应式布局：小屏幕时改为上下布局 */
@media (max-width: 900px) {
  .upload-container {
    flex-direction: column;
  }
  
  .form-section {
    flex: 1;
    min-width: auto;
    max-width: 100%;
    margin-bottom: 20px;
  }
  
  .preview-section {
    flex: 1;
    min-width: auto;
  }
}
</style>

<template>
  <div class="table-container">
    <el-table :data="fileListData" border class="_el-table" >
      <el-table-column prop="type" label="主标题" width="300" />
      <el-table-column prop="title" label="文章标题" width="300" />
      <el-table-column prop="updated_at" label="更新时间" width="220" />
      <el-table-column label="操作" width="150">
        <template #default="scope">
          <el-button
              type="danger"
              :icon="Delete"
              size="small"
              @click="handleDelete(scope.row)"
              :disabled="delFileLoading"
          >
            {{ delFileLoading ? '操作中...' : '删除' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="fileListData.length === 0" description="暂无文件" />
  </div>


</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {Delete} from "@element-plus/icons-vue";
import {useFileListStore} from "@/stores/fileList.js";
import {storeToRefs} from "pinia";
import api from "@/utils/api.js";

// 获取文件列表
const fileListStore = useFileListStore()
const { fileListData } = storeToRefs(fileListStore)

onMounted(() => {
  fileListStore.fetchDocs()
})

const delFileLoading = ref(false);
// 删除文件
const deleteFile = (fileId) => api.delete(`/docs/${fileId}`)
    .then((res) => {
    })
    .catch((err) => {
      ElMessage.error('文件删除失败')
    })
    .finally(() => {
      delFileLoading.value = false;
    });

// 删除文件
const handleDelete = async (file) => {
  delFileLoading.value = true
  ElMessageBox.confirm(
      `确定要删除文件 "${file.title}" 吗？`,
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
  )
      .then(async () => {
        try {
          await deleteFile(file.id);
          ElMessage.success('文件删除成功');
          fileListStore.fetchDocs()
        } catch (err) {
          delFileLoading.value = false;
          ElMessage.error('文件删除失败');
        }
      })
      .catch(() => {
        delFileLoading.value = false;
        ElMessage.info('已取消删除');
      });
};

</script>

<style scoped>


._el-table {
  margin-top: 20px;

  flex: 1;
  height: 100%;
}

.table-container {
  display: flex;
  flex: 1;
  padding: 20px;
}
</style>

import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from "@/utils/api.js";

export const useFileListStore = defineStore('fileList', () => {
    const data = ref([]);
    const typesData = ref([]);
    const loading = ref(true);
    const currentDoc = ref(null);

    const dataRefresh = () => {
        loading.value = true
        return api.get('/docs')
            .then(res => {
                // 置顶笔记优先（pinned_until 未过期）
                data.value = (res.data || []).slice().sort((a, b) => {
                    const pa = a.pinned_until && new Date(a.pinned_until) > new Date() ? 1 : 0
                    const pb = b.pinned_until && new Date(b.pinned_until) > new Date() ? 1 : 0
                    return pb - pa
                });
                // 反转数据以确保较旧的类型在 Set 中先出现 (假设 API 返回最新的在先)
                // 这确保了新类型 (后添加的) 出现在列表末尾
                const reversedData = [...data.value].reverse();
                const set = new Set(reversedData.map(item => item.type));
                typesData.value = Array.from(set).map(t => ({ value: t }));
                return '获取成功';
            })
            .catch(() => {
                return '获取失败';
            })
            .finally(() => {
                loading.value = false;
            });
    }

    const fetchDocs = () => dataRefresh();

    const fetchDoc = async (id) => {
        try {
            const res = await api.get(`/docs/${id}`);
            currentDoc.value = res.data;
            return currentDoc.value;
        } catch (e) {
            throw e;
        }
    }
    const fetchDocByKey = async (key) => {
        try {
            const res = await api.get(`/docs/by-key/${key}`);
            currentDoc.value = res.data;
            return currentDoc.value;
        } catch (e) {
            throw e;
        }
    }

    const getData = () => {
        return data.value;
    }

    const getLoading = () => {
        return loading.value;
    }

    return {
        fileListData: data,
        fileListLoading: loading,
        typesData,
        currentDoc,
        dataRefresh,
        fetchDocs,
        fetchDoc,
        fetchDocByKey,
        getData,
        getLoading,
    };
});

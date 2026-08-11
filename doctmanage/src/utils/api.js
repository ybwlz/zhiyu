import axios from 'axios';

const instance = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// 请求自动携带登录 token
instance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('kb_token');
    if (token) {
      config.headers.Authorization = 'Bearer ' + token;
    }
    // 动态数据不命中浏览器 HTTP 缓存（后端已对动态接口返回 no-store，此处双保险）
    if (config.method === 'get') {
      config.headers['Cache-Control'] = 'no-cache';
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 401 时清除本地登录态（登录接口本身的 401 除外，由登录页处理）
instance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response &&
      error.response.status === 401 &&
      !String(error.config.url).includes('/auth/login') &&
      !String(error.config.url).includes('/auth/register')
    ) {
      localStorage.removeItem('kb_token');
      localStorage.removeItem('kb_user');
    }
    return Promise.reject(error);
  }
);

export default instance;
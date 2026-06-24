import axios from 'axios';

// Vite 개발 프록시 또는 직접 연결을 지원하도록 백엔드 베이스 URL을 설정합니다.
const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: BASE_URL,
});

// 모든 API 요청 전에 X-User-Id 헤더를 동적으로 주입하는 인터셉터입니다.
apiClient.interceptors.request.use(
  (config) => {
    const userId = localStorage.getItem('argos_user_id');
    if (userId) {
      config.headers['X-User-Id'] = userId;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

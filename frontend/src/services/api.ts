/** API 客户端。 */

import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "";

export const httpClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const msg =
        error.response.data?.detail || error.response.data?.error || "请求处理失败";
      console.error("API 错误：", msg);
    }
    return Promise.reject(error);
  }
);

/** 将 API 错误转换为中文消息。 */

import axios from "axios";

const translateDriverError = (detail: string): string => {
  let text = detail
    .replace(
      /Can't connect to MySQL server on '([^']+)'/g,
      "无法连接到 MySQL 服务器 '$1'"
    )
    .replace(
      /Access denied for user '([^']+)'@'([^']+)' \(using password: YES\)/g,
      "用户 '$1'@'$2' 访问被拒绝（已使用密码）"
    )
    .replace(
      /Access denied for user '([^']+)'@'([^']+)' \(using password: NO\)/g,
      "用户 '$1'@'$2' 访问被拒绝（未使用密码）"
    )
    .replace(/Unknown database '([^']+)'/g, "数据库 '$1' 不存在")
    .replace(
      /password authentication failed for user "([^"]+)"/gi,
      '用户 "$1" 的密码认证失败'
    )
    .replace(/database "([^"]+)" does not exist/gi, '数据库 "$1" 不存在')
    .replace(/connection refused/gi, "连接被拒绝")
    .replace(/connection timed out/gi, "连接超时")
    .replace(/name or service not known/gi, "无法解析主机名");
  return text;
};

const KNOWN_PATTERNS: Array<[string, string]> = [
  ["Connection test failed:", "数据库连接测试失败："],
  ["Database connection", "数据库连接"],
  ["not found", "不存在"],
  ["Query execution failed", "查询执行失败"],
  ["Failed to generate SQL", "SQL 生成失败"],
];

export const extractErrorMessage = (
  error: unknown,
  fallback: string
): string => {
  if (!axios.isAxiosError(error)) {
    return fallback;
  }

  const detail = error.response?.data?.detail;
  if (typeof detail !== "string" || !detail.trim()) {
    return fallback;
  }

  let translated = translateDriverError(detail);
  let matched = translated !== detail;
  KNOWN_PATTERNS.forEach(([source, target]) => {
    if (translated.includes(source)) {
      translated = translated.replace(source, target);
      matched = true;
    }
  });

  return matched ? translated : `${fallback}：${detail}`;
};

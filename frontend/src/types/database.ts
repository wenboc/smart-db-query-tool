/** 数据库连接相关类型定义。 */

export type DatabaseType = "postgresql" | "mysql";

export interface ConnectionInfo {
  name: string;
  url: string;
  dbType: DatabaseType;
  description?: string | null;
  createdAt: string;
  updatedAt: string;
  lastConnectedAt?: string | null;
  status: "active" | "inactive" | "error";
}

export interface ConnectionPayload {
  url: string;
  dbType: DatabaseType;
  description?: string | null;
}

export interface ConnectionFormValues {
  name: string;
  dbType: DatabaseType;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  description?: string;
}

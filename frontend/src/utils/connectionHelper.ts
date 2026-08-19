/** 连接工具函数。 */

import { ConnectionFormValues, DatabaseType } from "../types/database";

export const DEFAULT_PORTS: Record<DatabaseType, number> = {
  postgresql: 5432,
  mysql: 3306,
};

export const FORM_DEFAULTS: Partial<ConnectionFormValues> = {
  dbType: "postgresql",
  host: "localhost",
  port: DEFAULT_PORTS.postgresql,
};

export const getDefaultPort = (dbType: DatabaseType): number =>
  DEFAULT_PORTS[dbType];

export const buildConnectionUrl = (values: ConnectionFormValues): string => {
  const username = encodeURIComponent(values.username.trim());
  const password = encodeURIComponent(values.password);
  const database = encodeURIComponent(values.database.trim());
  const rawHost = values.host.trim();
  const host =
    rawHost.includes(":") && !rawHost.startsWith("[") ? `[${rawHost}]` : rawHost;

  return `${values.dbType}://${username}:${password}@${host}:${values.port}/${database}`;
};

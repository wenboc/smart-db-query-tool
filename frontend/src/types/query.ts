/** 查询执行相关类型定义。 */

export interface ColumnMeta {
  name: string;
  dataType: string;
}

export interface QueryOutput {
  columns: ColumnMeta[];
  rows: Record<string, any>[];
  rowCount: number;
  executionTimeMs: number;
  sql: string;
}

export interface QueryRequest {
  sql: string;
}

export interface HistoryRecord {
  id: number;
  databaseName: string;
  sqlText: string;
  executedAt: string;
  executionTimeMs?: number | null;
  rowCount?: number | null;
  success: boolean;
  errorMessage?: string | null;
  querySource: "manual" | "natural_language";
}

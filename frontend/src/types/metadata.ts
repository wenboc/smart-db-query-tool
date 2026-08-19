/** 数据库元数据类型定义。 */

export interface ColumnDef {
  name: string;
  dataType: string;
  nullable: boolean;
  primaryKey: boolean;
  unique?: boolean;
  defaultValue?: string | null;
  comment?: string | null;
}

export interface TableDef {
  name: string;
  type: "table" | "view";
  columns: ColumnDef[];
  rowCount?: number | null;
  schemaName?: string;
}

export interface SchemaInfo {
  databaseName: string;
  tables: TableDef[];
  views: TableDef[];
  fetchedAt: string;
  isStale: boolean;
}

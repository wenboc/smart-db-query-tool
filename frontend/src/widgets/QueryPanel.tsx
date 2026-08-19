/** 查询面板 — SQL 编辑器 + 结果展示。 */

import React, { useRef } from "react";
import {
  Box,
  Button,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Typography,
  Chip,
} from "@mui/material";
import {
  PlayArrow as RunIcon,
  Download as DownloadIcon,
} from "@mui/icons-material";
import Editor, { type Monaco } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import { QueryOutput } from "../types/query";

interface QueryPanelProps {
  sql: string;
  onSqlChange: (value: string) => void;
  onExecute: () => void;
  executing: boolean;
  result: QueryOutput | null;
  onExportCSV: () => void;
  onExportJSON: () => void;
  dbName: string;
}

export const QueryPanel: React.FC<QueryPanelProps> = ({
  sql,
  onSqlChange,
  onExecute,
  executing,
  result,
  onExportCSV,
  onExportJSON,
  dbName,
}) => {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const [page, setPage] = React.useState(0);
  const [rowsPerPage, setRowsPerPage] = React.useState(50);

  const handleMount = (ed: editor.IStandaloneCodeEditor, monaco: Monaco) => {
    editorRef.current = ed;
    monaco.editor.defineTheme("db-explorer-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [],
      colors: {
        "editor.background": "#0d1117",
        "editor.foreground": "#c9d1d9",
      },
    });
    monaco.editor.setTheme("db-explorer-dark");

    ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
      onExecute();
    });
  };

  const columns = result?.columns || [];
  const rows = result?.rows || [];

  return (
    <Stack spacing={2} sx={{ flex: 1, overflow: "auto" }}>
      {/* SQL 编辑器 */}
      <Paper sx={{ p: 0, overflow: "hidden" }}>
        <Box sx={{ display: "flex", alignItems: "center", px: 2, py: 1, borderBottom: 1, borderColor: "divider" }}>
          <Typography variant="subtitle2" sx={{ flex: 1 }}>
            SQL 编辑器
          </Typography>
          <Chip label="Ctrl+Enter 执行" size="small" variant="outlined" sx={{ mr: 1 }} />
          <Button
            variant="contained"
            startIcon={<RunIcon />}
            onClick={onExecute}
            disabled={executing}
            size="small"
          >
            {executing ? "执行中..." : "执行"}
          </Button>
        </Box>
        <Editor
          height="200px"
          defaultLanguage="sql"
          value={sql}
          onChange={(v) => onSqlChange(v || "")}
          onMount={handleMount}
          options={{
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 14,
            lineNumbers: "on",
            automaticLayout: true,
            tabSize: 2,
            wordWrap: "on",
            lineHeight: 22,
          }}
        />
      </Paper>

      {/* 查询结果 */}
      {result && (
        <Paper sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <Box sx={{ display: "flex", alignItems: "center", px: 2, py: 1, borderBottom: 1, borderColor: "divider" }}>
            <Typography variant="subtitle2" sx={{ flex: 1 }}>
              查询结果
            </Typography>
            <Chip
              label={`${result.rowCount} 行 | ${result.executionTimeMs} 毫秒`}
              size="small"
              color="success"
              sx={{ mr: 1 }}
            />
            <Button size="small" startIcon={<DownloadIcon />} onClick={onExportCSV}>
              CSV
            </Button>
            <Button size="small" startIcon={<DownloadIcon />} onClick={onExportJSON}>
              JSON
            </Button>
          </Box>
          <TableContainer sx={{ flex: 1 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  {columns.map((col) => (
                    <TableCell
                      key={col.name}
                      sx={{ fontWeight: 700, whiteSpace: "nowrap", bgcolor: "background.paper" }}
                    >
                      {col.name}
                      <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
                        {col.dataType}
                      </Typography>
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage).map((row, i) => (
                  <TableRow key={i} hover>
                    {columns.map((col) => (
                      <TableCell key={col.name} sx={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>
                        {row[col.name] === null ? (
                          <Typography variant="body2" color="text.disabled" component="span">
                            NULL
                          </Typography>
                        ) : (
                          String(row[col.name])
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div"
            count={rows.length}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[10, 25, 50, 100]}
            labelRowsPerPage="每页行数"
          />
        </Paper>
      )}
    </Stack>
  );
};

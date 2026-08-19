/** 主面板视图 — 顶部导航 + 左右分栏布局。 */

import {
    Add as AddIcon,
    CheckCircle as CheckIcon,
    Delete as DeleteIcon,
    Error as ErrorIcon,
    Explore as ExploreIcon,
    Refresh as RefreshIcon,
    Storage as StorageIcon,
    Terminal as TerminalIcon,
} from "@mui/icons-material";
import {
    Alert,
    AppBar,
    Box,
    Button,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    Drawer,
    IconButton,
    LinearProgress,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    MenuItem,
    Snackbar,
    Stack,
    TextField,
    Toolbar,
    Typography,
} from "@mui/material";
import React, { useEffect, useState } from "react";
import { httpClient } from "../services/api";
import { ConnectionFormValues, ConnectionInfo, DatabaseType } from "../types/database";
import { SchemaInfo, TableDef } from "../types/metadata";
import { QueryOutput } from "../types/query";
import { buildConnectionUrl, DEFAULT_PORTS, FORM_DEFAULTS } from "../utils/connectionHelper";
import { extractErrorMessage } from "../utils/errorTranslator";
import { QueryPanel } from "../widgets/QueryPanel";
import { SchemaBrowser } from "../widgets/SchemaBrowser";

const DRAWER_WIDTH = 260;

const DB_TYPE_OPTIONS = [
  { label: "PostgreSQL", value: "postgresql" as DatabaseType },
  { label: "MySQL", value: "mysql" as DatabaseType },
];

export const Dashboard: React.FC = () => {
  const [connections, setConnections] = useState<ConnectionInfo[]>([]);
  const [activeDb, setActiveDb] = useState<string | null>(null);
  const [schema, setSchema] = useState<SchemaInfo | null>(null);
  const [queryResult, setQueryResult] = useState<QueryOutput | null>(null);
  const [sqlText, setSqlText] = useState("SELECT * FROM ");
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [toast, setToast] = useState<{ msg: string; severity: "success" | "error" | "info" | "warning" } | null>(null);

  const [formValues, setFormValues] = useState<Partial<ConnectionFormValues>>(FORM_DEFAULTS);

  useEffect(() => {
    fetchConnections();
  }, []);

  useEffect(() => {
    if (activeDb) {
      loadSchema();
    }
  }, [activeDb]);

  const fetchConnections = async () => {
    try {
      const res = await httpClient.get<ConnectionInfo[]>("/api/v1/dbs");
      setConnections(res.data);
      if (!activeDb && res.data.length > 0) {
        setActiveDb(res.data[0].name);
      }
    } catch (err) {
      setToast({ msg: extractErrorMessage(err, "加载数据库连接失败"), severity: "error" });
    }
  };

  const loadSchema = async () => {
    if (!activeDb) return;
    setLoading(true);
    try {
      const res = await httpClient.get<SchemaInfo>(`/api/v1/dbs/${activeDb}`);
      setSchema(res.data);
    } catch (err) {
      setToast({ msg: extractErrorMessage(err, "加载数据库结构失败"), severity: "error" });
    } finally {
      setLoading(false);
    }
  };

  const handleAddConnection = async () => {
    const v = formValues as ConnectionFormValues;
    if (!v.name || !v.host || !v.database || !v.username || !v.password) return;

    setAdding(true);
    try {
      const url = buildConnectionUrl(v);
      await httpClient.put(`/api/v1/dbs/${v.name}`, {
        url,
        dbType: v.dbType,
        description: v.description?.trim() || null,
      });
      setToast({ msg: "数据库连接添加成功", severity: "success" });
      setDialogOpen(false);
      setFormValues(FORM_DEFAULTS);
      await fetchConnections();
      setActiveDb(v.name);
    } catch (err) {
      setToast({ msg: extractErrorMessage(err, "添加数据库连接失败"), severity: "error" });
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteConnection = async (name: string) => {
    try {
      await httpClient.delete(`/api/v1/dbs/${name}`);
      setToast({ msg: "已删除连接", severity: "info" });
      if (activeDb === name) {
        const rest = connections.filter((c) => c.name !== name);
        setActiveDb(rest.length > 0 ? rest[0].name : null);
      }
      fetchConnections();
    } catch (err) {
      setToast({ msg: extractErrorMessage(err, "删除连接失败"), severity: "error" });
    }
  };

  const handleRefresh = async () => {
    if (!activeDb) return;
    try {
      await httpClient.post(`/api/v1/dbs/${activeDb}/refresh`);
      setToast({ msg: "元数据已刷新", severity: "success" });
      loadSchema();
    } catch (err) {
      setToast({ msg: extractErrorMessage(err, "刷新失败"), severity: "error" });
    }
  };

  const handleRunQuery = async () => {
    if (!activeDb || !sqlText.trim()) {
      setToast({ msg: "请输入 SQL 查询", severity: "warning" });
      return;
    }
    setExecuting(true);
    try {
      const res = await httpClient.post<QueryOutput>(
        `/api/v1/dbs/${activeDb}/query`,
        { sql: sqlText.trim() }
      );
      setQueryResult(res.data);
      setToast({
        msg: `查询成功：${res.data.rowCount} 行，耗时 ${res.data.executionTimeMs} 毫秒`,
        severity: "success",
      });
    } catch (err) {
      setToast({ msg: extractErrorMessage(err, "查询执行失败"), severity: "error" });
      setQueryResult(null);
    } finally {
      setExecuting(false);
    }
  };

  const handleTableSelect = (table: TableDef) => {
    setSqlText(`SELECT * FROM ${table.schemaName || "public"}.${table.name} LIMIT 100`);
  };

  const handleExportCSV = () => {
    if (!queryResult || queryResult.rows.length === 0) return;
    const headers = queryResult.columns.map((c) => c.name);
    const csvRows = [headers.join(",")];
    queryResult.rows.forEach((row) => {
      const vals = headers.map((h) => {
        const v = row[h];
        if (v === null || v === undefined) return "";
        const s = String(v);
        if (s.includes(",") || s.includes('"') || s.includes("\n")) {
          return `"${s.replace(/"/g, '""')}"`;
        }
        return s;
      });
      csvRows.push(vals.join(","));
    });
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${activeDb}_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const handleExportJSON = () => {
    if (!queryResult || queryResult.rows.length === 0) return;
    const blob = new Blob([JSON.stringify(queryResult.rows, null, 2)], {
      type: "application/json;charset=utf-8;",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${activeDb}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const updateForm = (field: string, value: any) => {
    setFormValues((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "dbType") {
        next.port = DEFAULT_PORTS[value as DatabaseType];
      }
      return next;
    });
  };

  return (
    <Box sx={{ display: "flex", height: "100vh" }}>
      {/* 侧边栏 — 连接列表 */}
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": {
            width: DRAWER_WIDTH,
            boxSizing: "border-box",
          },
        }}
      >
        <Toolbar sx={{ justifyContent: "space-between" }}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <ExploreIcon color="primary" />
            <Typography variant="h6" noWrap>
              智能数据库查询工具
            </Typography>
          </Stack>
        </Toolbar>
        <Divider />
        <Box sx={{ p: 1 }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            fullWidth
            onClick={() => setDialogOpen(true)}
            sx={{ mb: 1 }}
          >
            新建连接
          </Button>
        </Box>
        <Divider />
        <List sx={{ flex: 1, overflow: "auto" }}>
          {connections.map((conn) => (
            <ListItemButton
              key={conn.name}
              selected={activeDb === conn.name}
              onClick={() => setActiveDb(conn.name)}
              sx={{ borderRadius: 1, mx: 0.5, mb: 0.5 }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>
                {conn.status === "active" ? (
                  <CheckIcon sx={{ color: "success.main", fontSize: 18 }} />
                ) : (
                  <ErrorIcon sx={{ color: "error.main", fontSize: 18 }} />
                )}
              </ListItemIcon>
              <ListItemText
                primary={conn.name}
                primaryTypographyProps={{ fontSize: 14, fontWeight: 600 }}
                secondary={conn.description}
                secondaryTypographyProps={{ fontSize: 11, noWrap: true }}
              />
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteConnection(conn.name);
                }}
              >
                <DeleteIcon fontSize="small" color="error" />
              </IconButton>
            </ListItemButton>
          ))}
        </List>
      </Drawer>

      {/* 主内容区 */}
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* 顶栏 */}
        <AppBar position="static" color="default" elevation={0} sx={{ bgcolor: "background.paper" }}>
          <Toolbar variant="dense">
            <StorageIcon sx={{ mr: 1, color: "primary.main" }} />
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              {activeDb ? activeDb.toUpperCase() : "请选择数据库"}
            </Typography>
            {activeDb && (
              <Stack direction="row" spacing={1} alignItems="center">
                {schema && (
                  <>
                    <Chip label={`${schema.tables.length} 表`} size="small" color="primary" variant="outlined" />
                    <Chip label={`${schema.views.length} 视图`} size="small" color="secondary" variant="outlined" />
                    {queryResult && (
                      <Chip
                        label={`${queryResult.rowCount} 行 | ${queryResult.executionTimeMs} 毫秒`}
                        size="small"
                        color="success"
                      />
                    )}
                  </>
                )}
                <IconButton onClick={handleRefresh} title="刷新元数据">
                  <RefreshIcon />
                </IconButton>
              </Stack>
            )}
          </Toolbar>
        </AppBar>

        {loading && <LinearProgress />}

        {!activeDb ? (
          <Box sx={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Stack alignItems="center" spacing={2}>
              <TerminalIcon sx={{ fontSize: 64, color: "text.secondary" }} />
              <Typography variant="h5" color="text.secondary">
                选择或添加数据库连接
              </Typography>
            </Stack>
          </Box>
        ) : (
          <Box sx={{ flex: 1, display: "flex", overflow: "hidden" }}>
            {/* 左侧 Schema 浏览器 */}
            <Box sx={{ width: 320, borderRight: 1, borderColor: "divider", overflow: "auto" }}>
              {schema && (
                <SchemaBrowser
                  schema={schema}
                  onTableClick={handleTableSelect}
                />
              )}
            </Box>

            {/* 右侧查询面板 */}
            <Box sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto", p: 2 }}>
              <QueryPanel
                sql={sqlText}
                onSqlChange={setSqlText}
                onExecute={handleRunQuery}
                executing={executing}
                result={queryResult}
                onExportCSV={handleExportCSV}
                onExportJSON={handleExportJSON}
                dbName={activeDb}
              />
            </Box>
          </Box>
        )}
      </Box>

      {/* 新建连接弹窗 */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>新建数据库连接</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="连接名称"
              value={formValues.name || ""}
              onChange={(e) => updateForm("name", e.target.value)}
              required
            />
            <TextField
              label="数据库类型"
              select
              value={formValues.dbType || "postgresql"}
              onChange={(e) => updateForm("dbType", e.target.value)}
            >
              {DB_TYPE_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
            <Stack direction="row" spacing={2}>
              <TextField
                label="主机"
                value={formValues.host || ""}
                onChange={(e) => updateForm("host", e.target.value)}
                required
                sx={{ flex: 3 }}
              />
              <TextField
                label="端口"
                type="number"
                value={formValues.port || 5432}
                onChange={(e) => updateForm("port", parseInt(e.target.value, 10))}
                required
                sx={{ flex: 1 }}
              />
            </Stack>
            <TextField
              label="数据库名称"
              value={formValues.database || ""}
              onChange={(e) => updateForm("database", e.target.value)}
              required
            />
            <Stack direction="row" spacing={2}>
              <TextField
                label="用户名"
                value={formValues.username || ""}
                onChange={(e) => updateForm("username", e.target.value)}
                required
                sx={{ flex: 1 }}
              />
              <TextField
                label="密码"
                type="password"
                value={formValues.password || ""}
                onChange={(e) => updateForm("password", e.target.value)}
                required
                sx={{ flex: 1 }}
              />
            </Stack>
            <TextField
              label="说明（可选）"
              value={formValues.description || ""}
              onChange={(e) => updateForm("description", e.target.value)}
              multiline
              rows={2}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>取消</Button>
          <Button variant="contained" onClick={handleAddConnection} disabled={adding}>
            {adding ? "连接中..." : "测试并添加"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 提示条 */}
      {toast && (
        <Snackbar
          open
          autoHideDuration={4000}
          onClose={() => setToast(null)}
          anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        >
          <Alert severity={toast.severity} onClose={() => setToast(null)} variant="filled">
            {toast.msg}
          </Alert>
        </Snackbar>
      )}
    </Box>
  );
};

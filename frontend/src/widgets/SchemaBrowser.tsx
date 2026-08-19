/** 数据库结构浏览器 — 树形展示表、视图、列。 */

import React, { useMemo, useState } from "react";
import {
  Box,
  Typography,
  TextField,
  InputAdornment,
  Collapse,
  IconButton,
  Chip,
  Stack,
} from "@mui/material";
import {
  Search as SearchIcon,
  TableChart as TableIcon,
  ViewColumn as ViewIcon,
  ExpandMore as ExpandMoreIcon,
  ChevronRight as ChevronRightIcon,
  VpnKey as KeyIcon,
} from "@mui/icons-material";
import { SchemaInfo, TableDef } from "../types/metadata";

interface SchemaBrowserProps {
  schema: SchemaInfo;
  onTableClick?: (table: TableDef) => void;
}

export const SchemaBrowser: React.FC<SchemaBrowserProps> = ({
  schema,
  onTableClick,
}) => {
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ tables: true, views: false });

  const toggleSection = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const filteredTables = useMemo(() => {
    if (!filter) return schema.tables;
    const q = filter.toLowerCase();
    return schema.tables.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.columns.some((c) => c.name.toLowerCase().includes(q))
    );
  }, [schema.tables, filter]);

  const filteredViews = useMemo(() => {
    if (!filter) return schema.views;
    const q = filter.toLowerCase();
    return schema.views.filter(
      (v) =>
        v.name.toLowerCase().includes(q) ||
        v.columns.some((c) => c.name.toLowerCase().includes(q))
    );
  }, [schema.views, filter]);

  const renderTableItem = (item: TableDef, type: "table" | "view") => (
    <Box key={`${type}-${item.name}`} sx={{ mb: 0.5 }}>
      <Box
        onClick={() => onTableClick?.(item)}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 0.5,
          px: 1.5,
          py: 0.5,
          cursor: onTableClick ? "pointer" : "default",
          borderRadius: 1,
          "&:hover": { bgcolor: "action.hover" },
        }}
      >
        {type === "table" ? (
          <TableIcon sx={{ fontSize: 16, color: "primary.main" }} />
        ) : (
          <ViewIcon sx={{ fontSize: 16, color: "secondary.main" }} />
        )}
        <Typography variant="body2" sx={{ fontWeight: 600, flex: 1 }}>
          {item.name}
        </Typography>
        <Chip
          label={type === "table" ? "表" : "视图"}
          size="small"
          variant="outlined"
          color={type === "table" ? "primary" : "secondary"}
          sx={{ height: 20, fontSize: 10 }}
        />
        {item.rowCount !== null && item.rowCount !== undefined && (
          <Typography variant="caption" color="text.secondary">
            {item.rowCount}行
          </Typography>
        )}
      </Box>
      <Box sx={{ pl: 4 }}>
        {item.columns.map((col) => (
          <Box
            key={col.name}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 0.5,
              px: 0.5,
              py: 0.15,
            }}
          >
            {col.primaryKey && (
              <KeyIcon sx={{ fontSize: 12, color: "warning.main" }} />
            )}
            <Typography variant="caption" sx={{ fontWeight: 500 }}>
              {col.name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {col.dataType}
            </Typography>
            {!col.nullable && (
              <Chip label="NOT NULL" size="small" sx={{ height: 14, fontSize: 8 }} />
            )}
          </Box>
        ))}
      </Box>
    </Box>
  );

  return (
    <Box sx={{ p: 1 }}>
      <Box sx={{ px: 1, mb: 1 }}>
        <TextField
          placeholder="搜索表、列..."
          size="small"
          fullWidth
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ fontSize: 18 }} />
              </InputAdornment>
            ),
          }}
        />
      </Box>

      {/* 表 */}
      <Box>
        <Box
          onClick={() => toggleSection("tables")}
          sx={{ display: "flex", alignItems: "center", cursor: "pointer", px: 1, py: 0.5 }}
        >
          <IconButton size="small" sx={{ p: 0 }}>
            {expanded.tables ? <ExpandMoreIcon /> : <ChevronRightIcon />}
          </IconButton>
          <Typography variant="subtitle2" sx={{ ml: 0.5 }}>
            表 ({filteredTables.length})
          </Typography>
        </Box>
        <Collapse in={expanded.tables}>
          {filteredTables.map((t) => renderTableItem(t, "table"))}
        </Collapse>
      </Box>

      {/* 视图 */}
      <Box>
        <Box
          onClick={() => toggleSection("views")}
          sx={{ display: "flex", alignItems: "center", cursor: "pointer", px: 1, py: 0.5 }}
        >
          <IconButton size="small" sx={{ p: 0 }}>
            {expanded.views ? <ExpandMoreIcon /> : <ChevronRightIcon />}
          </IconButton>
          <Typography variant="subtitle2" sx={{ ml: 0.5 }}>
            视图 ({filteredViews.length})
          </Typography>
        </Box>
        <Collapse in={expanded.views}>
          {filteredViews.map((v) => renderTableItem(v, "view"))}
        </Collapse>
      </Box>
    </Box>
  );
};

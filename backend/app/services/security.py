import logging, os, sqlglot
from dataclasses import dataclass, field
from sqlglot import exp
from app.models.database import DatabaseType

logger = logging.getLogger(__name__)

class SecurityViolationError(Exception):
    def __init__(self, message: str, detail=None):
        super().__init__(message)
        self.detail = detail or {}

@dataclass
class SecurityPolicy:
    connection_name: str
    db_type: DatabaseType
    deny_tables: list = field(default_factory=list)
    sensitive_columns: dict = field(default_factory=dict)
    allow_explain: bool = False
    max_tables_per_query: int = 0
    max_columns_per_query: int = 0

    def check_explain(self, sql):
        stripped = sql.strip().lstrip("(").lstrip()
        if stripped.upper().startswith("EXPLAIN") and not self.allow_explain:
            raise SecurityViolationError("EXPLAIN 查询已被安全策略禁止", {"reason": "explain_blocked"})

    def _extract_tables(self, parsed):
        tables = []
        for n in parsed.find_all(exp.Table):
            parts = [n.name]
            if n.args.get("db"): parts.insert(0, str(n.args["db"]))
            tables.append(".".join(parts))
        seen, uniq = set(), []
        for t in tables:
            if t not in seen: seen.add(t); uniq.append(t)
        return uniq

    def _extract_columns(self, parsed):
        cols = []
        for c in parsed.find_all(exp.Column):
            ta = str(c.args["table"].name) if c.args.get("table") else ""
            cols.append((ta, c.name))
        seen, uniq = set(), []
        for c in cols:
            if c not in seen: seen.add(c); uniq.append(c)
        return uniq

    def _alias_map(self, parsed):
        m = {}
        for n in parsed.find_all(exp.Table):
            a = n.args.get("alias")
            if a and a.name:
                parts = [n.name]
                if n.args.get("db"): parts.insert(0, str(n.args["db"]))
                m[a.name] = ".".join(parts)
        return m

    def enforce(self, sql):
        self.check_explain(sql)
        if not (self.deny_tables or self.sensitive_columns or self.max_tables_per_query or self.max_columns_per_query):
            return
        dialect = "postgres" if self.db_type == DatabaseType.POSTGRESQL else "mysql"
        try: parsed = sqlglot.parse_one(sql, dialect=dialect)
        except Exception as e:
            logger.debug("Security parse skip: %s", e); return
        tables = self._extract_tables(parsed)
        columns = self._extract_columns(parsed)
        alias_map = self._alias_map(parsed)
        deny_set = set(self.deny_tables)
        for t in tables:
            if t in deny_set or t.split(".")[-1] in deny_set:
                raise SecurityViolationError(f"表 '{t}' 被安全策略禁止访问", {"blocked_table": t})
        if self.max_tables_per_query > 0 and len(tables) > self.max_tables_per_query:
            raise SecurityViolationError(f"单次查询最多 {self.max_tables_per_query} 张表", {"max": self.max_tables_per_query, "actual": len(tables)})
        for ta, cn in columns:
            real = alias_map.get(ta, ta) if ta else ""
            for dt, sens in self.sensitive_columns.items():
                short = dt.split(".")[-1]
                if (real == dt or real == short or (not real and short not in alias_map)) and cn in sens:
                    raise SecurityViolationError(f"列 '{dt}.{cn}' 为敏感列", {"blocked": f"{dt}.{cn}"})
        if self.max_columns_per_query > 0 and len(columns) > self.max_columns_per_query:
            raise SecurityViolationError(f"单次查询最多 {self.max_columns_per_query} 列", {"max": self.max_columns_per_query, "actual": len(columns)})

    @classmethod
    def from_connection_name(cls, name, db_type):
        def _env(n): return os.environ.get(n, "")
        def _split(v): return [s.strip() for s in v.split(",") if s.strip()]
        def _parse_sens(v):
            r = {}
            for chunk in v.split(";"):
                chunk = chunk.strip()
                if not chunk or ":" not in chunk: continue
                t, cols = chunk.split(":", 1)
                r[t.strip()] = [c.strip() for c in cols.split(",") if c.strip()]
            return r
        suffix = name.upper().replace("-", "_")
        def pick(p):
            for s in (suffix, db_type.value.upper(), "DEFAULT"):
                v = _env(f"{p}_{s}")
                if v: return v
            return ""
        return cls(
            connection_name=name, db_type=db_type,
            deny_tables=_split(pick("SECURITY_DENY_TABLES")),
            sensitive_columns=_parse_sens(pick("SECURITY_SENSITIVE_COLUMNS")),
            allow_explain=pick("SECURITY_ALLOW_EXPLAIN").lower() in ("1","true","yes","on"),
            max_tables_per_query=int(pick("SECURITY_MAX_TABLES") or "0"),
            max_columns_per_query=int(pick("SECURITY_MAX_COLUMNS") or "0"),
        )

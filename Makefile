.PHONY: help install dev backend frontend test lint format clean

# 变量
BACKEND_DIR = backend
FRONTEND_DIR = frontend
PYTHON = python3
UV = uv
NPM = npm

# 输出颜色
BLUE = \033[0;34m
GREEN = \033[0;32m
YELLOW = \033[0;33m
NC = \033[0m

help: ## Show this help message
	@echo "$(BLUE)智能数据库查询工具 - Makefile Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# 安装
install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install backend dependencies
	@echo "$(BLUE)Installing backend dependencies...$(NC)"
	cd $(BACKEND_DIR) && $(UV) sync

install-frontend: ## Install frontend dependencies
	@echo "$(BLUE)Installing frontend dependencies...$(NC)"
	cd $(FRONTEND_DIR) && $(NPM) install

# 开发服务器
dev: dev-backend dev-frontend ## Start both backend and frontend

dev-backend: ## Start backend development server
	@echo "$(BLUE)Starting backend server on http://localhost:8001$(NC)"
	cd $(BACKEND_DIR) && $(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

dev-frontend: ## Start frontend development server
	@echo "$(BLUE)Starting frontend server on http://localhost:5173$(NC)"
	cd $(FRONTEND_DIR) && $(NPM) run dev

# 后端命令
backend: dev-backend ## Alias for dev-backend

# 前端命令
frontend: dev-frontend ## Alias for dev-frontend

frontend-build: ## Build frontend for production
	@echo "$(BLUE)Building frontend...$(NC)"
	cd $(FRONTEND_DIR) && $(NPM) run build

# 测试
test: test-backend ## Run tests

test-backend: ## Run backend tests
	@echo "$(BLUE)Running backend tests...$(NC)"
	cd $(BACKEND_DIR) && $(UV) run pytest -v

# 代码质量
lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint backend code
	cd $(BACKEND_DIR) && $(UV) run ruff check app tests

lint-frontend: ## Lint frontend code
	cd $(FRONTEND_DIR) && $(NPM) run lint

format: format-backend format-frontend ## Format all code

format-backend: ## Format backend code
	cd $(BACKEND_DIR) && $(UV) run ruff format app tests

format-frontend: ## Format frontend code
	cd $(FRONTEND_DIR) && $(NPM) run lint -- --fix || true

# 清理
clean: clean-backend clean-frontend ## Clean all build artifacts

clean-backend: ## Clean backend artifacts
	@echo "$(BLUE)Cleaning backend...$(NC)"
	cd $(BACKEND_DIR) && \
		find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true && \
		find . -type f -name "*.pyc" -delete && \
		rm -rf .pytest_cache htmlcov .coverage

clean-frontend: ## Clean frontend artifacts
	@echo "$(BLUE)Cleaning frontend...$(NC)"
	cd $(FRONTEND_DIR) && rm -rf node_modules dist .vite

clean-db: ## Clean SQLite database
	@echo "$(YELLOW)WARNING: This will delete the SQLite database!$(NC)"
	rm -f ~/.db_explorer/db_explorer.db
	echo "$(GREEN)Database deleted$(NC)"

# 初始化
setup: install ## Initial setup
	@echo "$(GREEN)Setup complete!$(NC)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy backend/.env.example to backend/.env and add your OPENAI_API_KEY"
	@echo "  2. Run 'make dev' to start both servers"
	@echo "  3. Open http://localhost:5173 in your browser"

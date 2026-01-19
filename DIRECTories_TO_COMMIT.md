# Directories to Commit to Git

**Repository:** https://github.com/parimalpate123/agentic-sre  
**Purpose:** Clear guidance on what to commit vs exclude

---

## ✅ CORE APPLICATION CODE (MUST COMMIT)

### 1. `agent-core/`
- **Purpose:** Core agent intelligence using LangGraph
- **Contains:** Orchestrator, agents (Triage, Analysis, Diagnosis, Remediation), prompts, models, tests
- **Files:** `*.py`, `requirements.txt`, `README.md`
- **Status:** ✅ **COMMIT** - Essential application logic

### 2. `lambda-handler/`
- **Purpose:** AWS Lambda function handlers
- **Contains:** chat_handler.py, handler_router.py, analysis_handlers/, requirements.txt, build.sh
- **Exclude:** `package/`, `__pycache__/`, `lambda-deployment.zip` (already in .gitignore)
- **Status:** ✅ **COMMIT** - Source code only (build artifacts auto-excluded)

### 3. `mcp-client/`
- **Purpose:** Python client library for MCP server communication
- **Contains:** MCP client implementation, requirements.txt
- **Status:** ✅ **COMMIT** - Library code

### 4. `mcp-log-analyzer/`
- **Purpose:** MCP Log Analyzer Server
- **Contains:** Server implementation, Dockerfile, pyproject.toml, docs
- **Status:** ✅ **COMMIT** - MCP server code

### 5. `storage/`
- **Purpose:** DynamoDB abstraction layer
- **Contains:** Storage interface implementation, requirements.txt
- **Status:** ✅ **COMMIT** - Storage abstraction

### 6. `triage-assistant/`
- **Purpose:** React UI application
- **Contains:** Source code (src/), configuration (package.json, vite.config.js, eslint.config.js)
- **Exclude:** `dist/`, `node_modules/`, `.env.production` (already in .gitignore)
- **Status:** ✅ **COMMIT** - Source code only (build artifacts auto-excluded)

---

## ✅ INFRASTRUCTURE AS CODE (MUST COMMIT)

### 7. `infrastructure/`
- **Purpose:** Terraform Infrastructure as Code
- **Contains:** Terraform configuration files (*.tf), README.md
- **Exclude:** `terraform.tfstate*`, `tfplan`, `.terraform/` (already in .gitignore)
- **Status:** ✅ **COMMIT** - IaC definitions (state files auto-excluded)

---

## ✅ SCRIPTS & UTILITIES (SHOULD COMMIT)

### 8. `scripts/`
- **Purpose:** Deployment and utility scripts
- **Contains:** build-and-push-mcp.sh, deploy-infrastructure.sh, deploy-ui.sh, generate-sample-logs.sh, etc.
- **Status:** ✅ **COMMIT** - Automation scripts

### 9. Root-level scripts (`.sh` files)
- **Files:** deploy.sh, deploy-lambda.sh, deploy-mcp.sh, build-mcp-server.sh, check-*.sh, etc.
- **Status:** ✅ **COMMIT** - Deployment and management scripts

---

## ✅ DOCUMENTATION (SHOULD COMMIT)

### 10. `docs/`
- **Purpose:** Project documentation
- **Contains:** Architecture docs, guides, implementation plans, diagrams
- **Status:** ✅ **COMMIT** - Project documentation

### 11. Root-level markdown files
- **Files:** README.md, *.md files (guides, analysis documents, API guides)
- **Examples:** CHAT_API_GUIDE.md, POSTMAN_TESTING_GUIDE.md, OBSERVABILITY_GUIDE.md, etc.
- **Status:** ✅ **COMMIT** - Documentation

---

## ✅ CONFIGURATION FILES (MUST COMMIT)

### 12. Root configuration files
- **Files:** `.gitignore`, configuration JSON files
- **Status:** ✅ **COMMIT** - Project configuration

### 13. Configuration files in subdirectories
- **Files:** `package.json`, `requirements.txt`, `vite.config.js`, `Dockerfile`, `pyproject.toml`, `eslint.config.js`
- **Status:** ✅ **COMMIT** - Dependency and build configuration

---

## ✅ TEST & API DEFINITIONS (SHOULD COMMIT)

### 14. Test files
- **Files:** `test-*.py`, `test-*.sh`, test directories
- **Status:** ✅ **COMMIT** - Test scripts

### 15. API Collections
- **Files:** `*.postman_collection.json`
- **Status:** ✅ **COMMIT** - API test definitions

---

## ❌ DO NOT COMMIT (Already Excluded via .gitignore)

These are automatically excluded by `.gitignore`:

### Build Artifacts
- `lambda-handler/package/` - Compiled dependencies (3000+ files)
- `lambda-handler/lambda-deployment.zip` - Deployment package
- `triage-assistant/dist/` - Build output
- `triage-assistant/node_modules/` - NPM dependencies
- `__pycache__/` - Python cache directories
- `*.pyc`, `*.pyo` - Python compiled files

### State & Configuration Files
- `infrastructure/terraform.tfstate*` - Terraform state (contains AWS account ID)
- `infrastructure/tfplan` - Terraform plan file
- `.terraform/` - Terraform working directory
- `.env`, `.env.production`, `.env.local` - Environment files

### Output Files
- `outputs.txt` - Terraform outputs
- `response.json` - Test response file
- `validate-logs-output.txt` - Validation output
- `test-event.json` - Test event file
- `*.log` - Log files

---

## ⚠️ RECOMMENDED TO EXCLUDE (Not in .gitignore yet)

### 16. `temp-setup/`
- **Purpose:** Temporary/example code
- **Size:** 2852 files (757 Python, 485 PNG, 295 Markdown)
- **Contains:** Example code, reference implementations, sample projects
- **Recommendation:** ❌ **EXCLUDE** - Too large, appears temporary/reference material
- **Action Required:** Add `temp-setup/` to `.gitignore`

### 17. `ai-generated-md/`
- **Purpose:** AI-generated documentation
- **Recommendation:** ❌ **EXCLUDE** - Generated content, not source
- **Action Required:** Add `ai-generated-md/` to `.gitignore`

---

## 📋 QUICK REFERENCE CHECKLIST

### ✅ COMMIT THESE DIRECTORIES/FILES:

**Core Code:**
- [x] `agent-core/`
- [x] `lambda-handler/` (source files only)
- [x] `mcp-client/`
- [x] `mcp-log-analyzer/`
- [x] `storage/`
- [x] `triage-assistant/` (source files only)

**Infrastructure:**
- [x] `infrastructure/` (`.tf` files only)

**Scripts & Automation:**
- [x] `scripts/`
- [x] Root-level `.sh` files

**Documentation:**
- [x] `docs/`
- [x] Root-level `.md` files

**Configuration:**
- [x] `.gitignore`
- [x] `package.json`, `requirements.txt`, `pyproject.toml`, etc.
- [x] `Dockerfile`, `vite.config.js`, `eslint.config.js`

**Tests & APIs:**
- [x] Test files (`test-*.py`, `test-*.sh`)
- [x] `*.postman_collection.json`

### ❌ DO NOT COMMIT (Auto-excluded via .gitignore):

- [x] Build artifacts (`package/`, `dist/`, `node_modules/`, `__pycache__/`)
- [x] State files (`terraform.tfstate*`, `tfplan`)
- [x] Environment files (`.env*`)
- [x] Output files (`outputs.txt`, `response.json`, `*.log`)

### ⚠️ ADD TO .gitignore:

- [ ] `temp-setup/`
- [ ] `ai-generated-md/`

---

## 🚀 RECOMMENDED .gitignore UPDATE

Add these lines to your `.gitignore`:

```gitignore
# Temporary/Reference directories
temp-setup/
ai-generated-md/

# Additional output files (if not already present)
validate-logs-output.txt
```

---

## 📊 SIZE ESTIMATE

**Estimated commit size (excluding build artifacts):**
- Core code: ~50-100 files
- Infrastructure: ~15 files
- Scripts: ~15 files
- Documentation: ~30 files
- Configuration: ~10 files
- **Total: ~120-180 files** (reasonable size)

**If temp-setup/ is included:** +2852 files (not recommended)

---

## ✅ FINAL RECOMMENDATION

**Safe to commit:** All directories listed in "COMMIT THESE" section  
**Auto-excluded:** Everything in .gitignore (no action needed)  
**Action required:** Add `temp-setup/` and `ai-generated-md/` to `.gitignore` before committing

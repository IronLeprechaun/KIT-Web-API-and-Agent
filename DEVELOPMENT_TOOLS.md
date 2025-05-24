# KIT System - Development Tools & Workflows

This document outlines all the development tools and workflows available to make coding and updating the KIT system easier and more efficient.

## 🚀 Quick Start Commands

```bash
# Set up secure secrets (first time)
cd KIT_Web && python scripts/secrets_manager.py --setup

# Set up development environment
cd KIT_Web && python scripts/dev_setup.py --setup-all

# Initialize configurations
cd KIT_Web && python scripts/config_manager.py --init

# Run comprehensive tests
cd KIT_Web && python scripts/enhanced_tester.py --comprehensive

# Check system health
cd KIT_Web && python scripts/server_manager.py --health-check
```

## 📁 Directory Structure

```
KIT_Web/                     # Primary workspace
├── scripts/                 # Development automation scripts
│   ├── secrets_manager.py  # 🔐 Secure API key management
│   ├── dev_setup.py        # Environment setup & management
│   ├── config_manager.py   # Configuration & environment management
│   ├── enhanced_tester.py  # Comprehensive testing framework
│   ├── log_analyzer.py     # Log analysis & debugging
│   ├── server_manager.py   # Server start/stop/health management
│   └── enhanced_tester.py  # Comprehensive testing framework
├── .secrets/                # 🔐 Encrypted secrets storage (gitignored)
├── tests/                   # Test suites│   ├── api/                # API endpoint tests│   ├── database/           # Database tests│   └── backend/            # Backend unit tests
├── config.py               # System configuration
├── backend/                 # Python backend
├── frontend/                # React frontend
└── docs/                   # Documentation
```

## 🔐 **SECURITY FIRST: Secure Secrets Management**

### 1. Secure Secrets Manager (`secrets_manager.py`)

**Purpose**: Secure, encrypted storage of API keys and sensitive configuration data.

```bash
# Initial setup wizard (recommended)
python scripts/secrets_manager.py --setup

# Individual secret management
python scripts/secrets_manager.py --set GEMINI_API_KEY your_actual_key
python scripts/secrets_manager.py --get GEMINI_API_KEY
python scripts/secrets_manager.py --list
python scripts/secrets_manager.py --delete GEMINI_API_KEY

# Export to .env file (use with caution)
python scripts/secrets_manager.py --export-env backend/.env
```

**Security Features**:
- 🔐 AES encryption with PBKDF2 key derivation
- 🔑 Master password protection
- 📁 Restricted file permissions
- 🚫 Never commits to git (.gitignore protected)
- ⚡ Cross-platform compatibility

## 🛠️ Development Tools

### 2. Development Setup (`dev_setup.py`)

**Purpose**: Automates environment setup and common development tasks.

```bash
# Set up everything (recommended for new environments)
python scripts/dev_setup.py --setup-all

# Individual setup commands
python scripts/dev_setup.py --setup-backend    # Python venv & dependencies
python scripts/dev_setup.py --setup-frontend   # npm dependencies
python scripts/dev_setup.py --reset-db         # Clean database reset
python scripts/dev_setup.py --run-tests        # Run basic tests
python scripts/dev_setup.py --check-env        # Environment health check
```

**What it does**:
- ✅ Creates Python virtual environment
- ✅ Installs all dependencies 
- ✅ Resets database to clean state
- ✅ Verifies environment setup
- ✅ Runs basic tests

### 3. Configuration Manager (`config_manager.py`)

**Purpose**: Manages environment variables and deployment configurations with secure secrets integration.

```bash
# Initialize all configurations
python scripts/config_manager.py --init

# Switch environments (uses secure secrets by default)
python scripts/config_manager.py --env development
python scripts/config_manager.py --env testing
python scripts/config_manager.py --env production

# Use environment variables instead of secure secrets
python scripts/config_manager.py --env development --use-env-vars

# Check current configuration
python scripts/config_manager.py --check

# Generate sample environment file
python scripts/config_manager.py --sample
```

**Features**:
- 🔐 Secure secrets integration
- 🌍 Multiple environment support (dev/test/prod)
- 📁 Automatic .env file generation
- 🔍 Configuration validation
- 📋 Environment status checking

### 4. Enhanced Testing Framework (`enhanced_tester.py`)

**Purpose**: Comprehensive testing with detailed reporting and performance metrics.

```bash
# Run all tests (recommended)
python scripts/enhanced_tester.py --comprehensive

# Individual test suites
python scripts/enhanced_tester.py --database     # Database connectivity & schema
python scripts/enhanced_tester.py --backend      # Backend API health
python scripts/enhanced_tester.py --frontend     # Frontend availability
python scripts/enhanced_tester.py --api          # API endpoint functionality
python scripts/enhanced_tester.py --notes        # Note CRUD operations
python scripts/enhanced_tester.py --performance  # Performance benchmarks
```

**Test Coverage**:
- 🗄️ Database connection, schema, and basic operations
- 🔧 Backend API health and endpoint functionality
- ⚛️ Frontend availability and responsiveness
- 📝 Note creation, retrieval, and deletion
- ⚡ Performance metrics and response times
- 🔍 Automated issue detection

### 5. Log Analyzer (`log_analyzer.py`)

**Purpose**: Intelligent log analysis and debugging assistance.

```bash
# Show recent log activity
python scripts/log_analyzer.py --tail 100

# Find errors in last 24 hours
python scripts/log_analyzer.py --errors

# Database-related logs
python scripts/log_analyzer.py --db-errors

# Activity summary
python scripts/log_analyzer.py --summary

# Custom timeframe
python scripts/log_analyzer.py --errors --hours 6
```

**Features**:
- 🔍 Smart log parsing and filtering
- 🔴 Error detection and highlighting
- 📊 Activity summaries and statistics
- 🗄️ Database-specific log analysis
- ⏰ Time-based log filtering

### 6. Server Manager (`server_manager.py`)

**Purpose**: Manages backend and frontend servers with health monitoring.

```bash
# Health check (recommended first step)
python scripts/server_manager.py --health-check

# Start servers
python scripts/server_manager.py --start-backend
python scripts/server_manager.py --start-frontend
python scripts/server_manager.py --start-all

# Stop servers
python scripts/server_manager.py --stop-all

# Restart after changes
python scripts/server_manager.py --restart-all
```

**Health Checks**:
- ✅ Backend API connectivity
- ✅ Frontend responsiveness
- ✅ Database accessibility
- ✅ Port availability

## 🔄 Development Workflows

### 🆕 Starting Development (First Time - SECURE)

```bash
cd KIT_Web

# 1. Set up secure secrets (IMPORTANT!)
python scripts/secrets_manager.py --setup

# 2. Set up environment
python scripts/dev_setup.py --setup-all

# 3. Initialize configurations
python scripts/config_manager.py --init

# 4. Verify setup
python scripts/config_manager.py --check
python scripts/enhanced_tester.py --comprehensive
```

### 🔧 Daily Development Workflow

```bash
# 1. Start servers
python scripts/server_manager.py --start-all

# 2. Check system health
python scripts/server_manager.py --health-check

# 3. Make your changes...

# 4. Test changes
python scripts/enhanced_tester.py --comprehensive

# 5. Check logs if issues
python scripts/log_analyzer.py --errors

# 6. Stop servers when done
python scripts/server_manager.py --stop-all
```

### 🐛 Debugging Workflow

```bash
# 1. Check recent errors
python scripts/log_analyzer.py --errors --hours 1

# 2. Check system health
python scripts/enhanced_tester.py --comprehensive

# 3. Database issues?
python scripts/enhanced_tester.py --database
python scripts/log_analyzer.py --db-errors

# 4. Reset if needed
python scripts/dev_setup.py --reset-db

# 5. Performance issues?
python scripts/enhanced_tester.py --performance
```

### 🚀 Before Deploying

```bash
# 1. Switch to production config
python scripts/config_manager.py --env production

# 2. Run full test suite
python scripts/enhanced_tester.py --comprehensive

# 3. Check performance
python scripts/enhanced_tester.py --performance

# 4. Review logs
python scripts/log_analyzer.py --summary
```

## 🎯 Autonomous Testing Protocol

The system follows the **Cursor Rules** for autonomous testing:

### Before Making Changes
```bash
# Always run baseline tests first
cd KIT_Web && python scripts/enhanced_tester.py --comprehensive
```

### After Making Changes
```bash
# Run targeted tests for changed components
cd KIT_Web && python scripts/enhanced_tester.py --backend    # Backend changes
cd KIT_Web && python scripts/enhanced_tester.py --frontend   # Frontend changes
cd KIT_Web && python scripts/enhanced_tester.py --database   # Database changes

# Run full regression test
cd KIT_Web && python scripts/enhanced_tester.py --comprehensive
```

### Server Management Protocol
```bash
# Stop servers before schema changes
cd KIT_Web && python scripts/server_manager.py --stop-all

# Restart servers after config changes
cd KIT_Web && python scripts/server_manager.py --restart-all

# Check server health
cd KIT_Web && python scripts/server_manager.py --health-check
```

## 📊 Test Results & Reporting

All tools generate detailed reports:

- **Test Results**: `test_results.json` - Comprehensive test results with performance metrics
- **Log Analysis**: Console output with structured error reporting
- **Health Checks**: Real-time status with specific issue identification
- **Performance**: Response time metrics and benchmark comparisons

## 🔧 Troubleshooting

### Common Issues & Solutions

1. **"Connection refused" errors**:
   ```bash
   python scripts/server_manager.py --health-check
   python scripts/server_manager.py --start-all
   ```

2. **Database errors**:
   ```bash
   python scripts/dev_setup.py --reset-db
   python scripts/enhanced_tester.py --database
   ```

3. **Environment issues**:
   ```bash
   python scripts/config_manager.py --check
   python scripts/config_manager.py --init
   ```

4. **Dependency problems**:
   ```bash
   python scripts/dev_setup.py --setup-backend
   python scripts/dev_setup.py --setup-frontend
   ```

5. **Performance issues**:
   ```bash
   python scripts/enhanced_tester.py --performance
   python scripts/log_analyzer.py --summary
   ```

6. **Secrets management issues**:
   ```bash
   python scripts/secrets_manager.py --list
   python scripts/secrets_manager.py --setup
   ```

## 🛡️ Security Best Practices

1. **NEVER commit API keys to git**
2. **Always use the secure secrets manager for sensitive data**
3. **Use strong master passwords (8+ characters)**
4. **Regularly rotate API keys**
5. **Check .gitignore includes all sensitive files**
6. **Use environment-specific configurations**

## 🎯 Development Best Practices

1. **Always test before and after changes**
2. **Use health checks to verify system state**
3. **Check logs when debugging**
4. **Use appropriate environment configs**
5. **Reset database when schema changes**
6. **Monitor performance regularly**
7. **Keep secrets secure and encrypted**

## 📞 Getting Help

1. Check system health: `python scripts/server_manager.py --health-check`
2. Run comprehensive tests: `python scripts/enhanced_tester.py --comprehensive`
3. Analyze recent logs: `python scripts/log_analyzer.py --errors`
4. Check configuration: `python scripts/config_manager.py --check`
5. List secure secrets: `python scripts/secrets_manager.py --list`

---

**Remember**: 
- 🔐 **Security First**: Always use the secure secrets manager for API keys
- 📁 **Primary Workspace**: All development happens in `KIT_Web/` 
- 📚 **Reference Only**: Use `OLD_VERSION_KIT_PY/` for reference only
- 🚫 **Never Commit**: Sensitive data is protected by comprehensive .gitignore 
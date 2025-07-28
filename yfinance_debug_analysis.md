# SaneApe.com yfinance Production Error Analysis

## Executive Summary
SaneApe.com's stock analysis system broke in production with "Errno 5" and "no such table: _tz_kv" errors after working perfectly for multiple days. This document provides comprehensive analysis for debugging and resolution.

## Timeline of Events

### Phase 1: Working System (July 26-27, 2025)
- **Status**: Stock analysis system fully operational for multiple days
- **Features Working**: 
  - Standard stock analysis (6 requests/day)
  - Maximum Brain Analysis (2 requests/day) 
  - Income-focused analysis for ETFs
  - Real-time caching system
  - User subscription system with credits
- **Architecture**: Flask + SQLAlchemy + yfinance + OpenAI GPT-4o

### Phase 2: Feature Flag Issues (July 28, 2025 Early Morning)
- **Problem**: Subscription system suddenly stopped working
- **Root Cause**: Feature flags were disabled (stripe_payments=False, subscription_management=False)
- **Solution Applied**: Enabled all critical feature flags in feature_flags.py
- **Result**: Subscription system restored, but stock analysis remained broken

### Phase 3: Stock Analysis Breakdown (July 28, 2025)
- **Primary Error**: `[Errno 5] Input/output error` when calling yfinance
- **Secondary Error**: `no such table: _tz_kv` (timezone database table missing)
- **Impact**: Complete failure of all stock analysis endpoints
- **User Impact**: Production site unusable for core functionality

## Technical Error Analysis

### Error 1: Errno 5 (Input/output error)
```
OSError: [Errno 5] Input/output error
```
- **Meaning**: File system I/O operation failed
- **Context**: Occurs when yfinance tries to create/access SQLite cache database
- **Location**: yfinance internal database operations

### Error 2: Database Table Missing
```
no such table: _tz_kv
```
- **Meaning**: yfinance's timezone database table doesn't exist
- **Context**: yfinance uses SQLite for caching timezone data
- **Implication**: Database corruption or incomplete initialization

### Error 3: Environment Detection Issues
- **Problem**: Code was checking wrong environment variable (REPLIT_DEPLOYMENT vs REPLIT_ENVIRONMENT)
- **Impact**: Production environment not properly detected
- **Status**: ✅ FIXED - Now correctly detects production environment

## Attempted Solutions & Results

### Attempt 1: Cache Clearing
```bash
rm -rf /home/runner/workspace/.cache/py-yfinance
```
- **Result**: FAILED - Errors persisted
- **Issue**: Cache recreated with same corruption

### Attempt 2: Environment Variable Manipulation
```python
os.environ['YFINANCE_CACHE_DIR'] = '/tmp'
```
- **Result**: FAILED - Still tried to access corrupted database
- **Issue**: yfinance has hardcoded database paths

### Attempt 3: Monkey Patching Database Operations
```python
from peewee import Database
Database.create_tables = lambda self, *args, **kwargs: None
```
- **Result**: FAILED - "_tz_kv" error persisted
- **Issue**: Partial patching, other database operations still active

### Attempt 4: Direct API Replacement (REJECTED by User)
- **Approach**: Replace yfinance with direct Yahoo Finance API calls
- **User Requirement**: "WE MUST USE YFINANCE!!!"
- **Status**: Reverted back to yfinance

## Root Cause Hypothesis

### Primary Theory: SQLite Database Corruption
1. **Triggering Event**: Unknown system event corrupted yfinance's SQLite cache
2. **Database Location**: `/home/runner/workspace/.cache/py-yfinance/`
3. **Corrupted Component**: Timezone database table `_tz_kv`
4. **Impact**: yfinance cannot initialize timezone handling

### Secondary Theory: File System Permissions
1. **Issue**: Replit environment changed file permissions
2. **Impact**: yfinance cannot write to cache directory
3. **Evidence**: Errno 5 typically indicates permission or disk space issues

### Tertiary Theory: yfinance Version Conflict
1. **Issue**: Package update introduced incompatibility
2. **Impact**: Database schema mismatch
3. **Evidence**: System worked for days then suddenly broke

## Current System State

### Working Components ✅
- Flask application starts successfully
- Database (PostgreSQL) connections working
- User authentication system operational
- Subscription and payment system functional
- Feature flags properly enabled
- Admin dashboard accessible

### Broken Components ❌
- yfinance stock data fetching
- All stock analysis endpoints (/analyze)
- Technical indicator calculations
- Income-focused analysis
- Share page generation (depends on stock data)

## Investigation Commands Run

```bash
# Check for SQLite files
find /home/runner -name "*.sqlite*" -o -name "*.db"

# Check yfinance cache
ls -la /home/runner/workspace/.cache/py-yfinance/

# Test yfinance directly
python3 -c "import yfinance as yf; print(yf.Ticker('AAPL').history(period='5d'))"
```

## Next Steps for Resolution

### Step 1: Complete Database Analysis
- [ ] Identify all yfinance SQLite files
- [ ] Check database integrity with SQLite commands
- [ ] Examine schema of corrupted databases

### Step 2: Force Database Regeneration
- [ ] Remove ALL yfinance cache files
- [ ] Clear Python package cache
- [ ] Force yfinance to rebuild from scratch

### Step 3: Alternative Isolation
- [ ] Run yfinance in completely isolated environment
- [ ] Use temporary directories for all operations
- [ ] Disable ALL caching mechanisms

### Step 4: Package Verification
- [ ] Check exact yfinance version in production
- [ ] Compare with working development environment
- [ ] Consider downgrade if version mismatch found

## Critical Success Metrics

### Must Work:
1. `yf.Ticker('AAPL').history(period='5d')` returns data
2. All stock analysis endpoints return valid JSON
3. Technical indicators calculate properly
4. Income analysis works for ETFs
5. Caching system functions without errors

### Performance Requirements:
- Stock data fetch: < 10 seconds
- Full analysis generation: < 30 seconds
- Error rate: < 1% for valid tickers

## Emergency Rollback Plan

If yfinance cannot be fixed:
1. **User explicitly rejected direct API approach**
2. **Must find yfinance-compatible solution**
3. **Consider yfinance version downgrade**
4. **Investigate yfinance alternatives that maintain API compatibility**

## Contact Information

- **Primary Issue**: yfinance SQLite database corruption
- **Environment**: Replit production environment
- **Urgency**: HIGH - Core functionality completely broken
- **Timeline**: System worked for days, broke suddenly on July 28, 2025

---

*This analysis document should be updated as new information becomes available and solutions are attempted.*
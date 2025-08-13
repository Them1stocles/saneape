# SaneApe.com - AI Stock Analysis Platform

## Overview

SaneApe.com is a Flask-based web application providing AI-powered stock technical analysis. Its core purpose is to offer users AI-generated recommendations (buy/don't buy) based on historical data and technical indicators, leveraging OpenAI's GPT API. The project aims to deliver a reliable "sanity check" for traders, providing data-driven insights over emotional decisions, with future ambitions including user accounts, paid subscriptions, and expanded AI analysis capabilities.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Single-page application** built with HTML5, CSS3, and vanilla JavaScript.
- **Bootstrap 5** for responsive UI and mobile-first design.
- **Feather Icons** for consistent iconography.
- **Progressive enhancement** approach with client-side form validation.

### Backend Architecture
- **Flask** web framework utilizing SQLAlchemy ORM.
- **Modular design** separating concerns into `app.py`, `routes.py`, `models.py`, `stock_analyzer.py`, and `rate_limiter.py`.
- **SQLite database** for development, with PostgreSQL-ready configuration for production.
- **Database Design**: `RateLimit` for IP-based tracking and `StockAnalysis` for result storage.

### Core Features
- **Stock Analysis Engine**: Integrates `yfinance` for historical data (2 years), calculates standard technical indicators (SMA, EMA, RSI, MACD), and uses **OpenAI GPT-4.1** for AI analysis. Includes "Maximum Brain Analysis" with 35+ indicators and data summarization for API optimization.
- **Rate Limiting System**: IP-based rate limiting (2 standard, 1 Maximum Brain per day) persistent via database, with graceful error handling. Also supports credit-based rate limiting for authenticated users.
- **Security Features**: Environment-based configuration for sensitive data, input validation (ticker symbols), `ProxyFix` middleware for IP detection, and SQL injection protection via SQLAlchemy.
- **User Accounts & Payments**: Implements a robust user account system with Replit OAuth integration, a dual credit system (subscription and top-up credits), and a full-stack **Stripe payment system** for subscriptions and top-ups. Includes secure webhook processing and a comprehensive account dashboard.
- **Social Sharing**: Enables sharing of analysis results via unique URLs, with Open Graph meta tags for Twitter and Facebook, and dynamic content based on analysis.
- **Admin System**: Password-protected admin interface for monitoring usage, managing limits, and system controls.
- **Analytics**: Comprehensive Google Analytics integration with custom event tracking for key user interactions and conversion monitoring.

### Technical Implementation Details
- **Error Handling**: Robust try-catch blocks, graceful degradation, and comprehensive logging.
- **Performance**: Optimized imports, caching mechanisms (e.g., 6-hour analysis cache), and database indexing.
- **Scalability**: Architecture designed for future user accounts, paid tiers, and horizontal scaling.
- **Unicode Handling**: Comprehensive Unicode normalization for accurate display of AI recommendations across all parts of the application.

## External Dependencies

### APIs and Services
- **OpenAI GPT-4.1 API**: For AI-powered stock analysis.
- **Yahoo Finance (yfinance)**: For historical stock data retrieval.
- **Stripe**: For payment processing, subscriptions, and billing portal management.

### Python Packages
- **Flask**: Web framework.
- **SQLAlchemy**: Database ORM.
- **yfinance**: Python wrapper for Yahoo Finance API.
- **pandas/numpy**: Data manipulation and analysis.
- **openai**: OpenAI API client.

### Frontend Libraries
- **Bootstrap 5**: CSS framework.
- **Feather Icons**: Icon library.

## Recent Changes

### August 13, 2025 - Optimized GPT-5 Single-Call Maximum Brain Analysis
- **Refactored to Single-Call Architecture**: Replaced 3-tier system with single comprehensive API call to stay within 30,000 TPM GPT-5 limit
- **Token Optimization**: Reduced from ~30,000 tokens (3 calls) to ~10,000 tokens (1 call) while maintaining all analytical capabilities
- **Comprehensive Single Prompt**: All 35+ indicators analyzed in one request with institutional-grade requirements
- **GPT-5 Specific Features**: Verbosity controls (high), Context-Free Grammar for structured output, reasoning_effort (max) for complex analysis
- **Extended Timeout Handling**: 180-second timeouts for GPT-5, 90-second for GPT-4o fallback, exponential backoff with up to 5 retries
- **Dual Client Architecture**: Separate OpenAI clients for GPT-5 (primary) and GPT-4o (fallback) with optimized parameters
- **Production-Grade Error Handling**: Graceful fallback from GPT-5 to GPT-4o when unavailable, chunked analysis as final fallback
- **Validation System**: Comprehensive response validation ensuring all required fields present before accepting analysis
- **Zero Functionality Removal**: All features maintained, backwards compatible, more efficient within API limits

### August 11, 2025 - SSL Retry Logic & Multi-Call Fallback System
- **SSL Connection Retry Logic Implemented**: Extended retry system beyond rate limiting (HTTP 429) to handle SSL connection failures, timeouts, network errors, and handshake issues. Now retries up to 3 times with exponential backoff for all connection-related errors
- **Multi-Call Fallback System for Maximum Brain**: When Maximum Brain analysis fails twice due to connection issues, system automatically splits analysis into smaller chunks: core trend indicators (RSI, MACD, SMA, etc.) and volume indicators (OBV, ATR, MFI, etc.), then synthesizes results. Reduces payload size and connection time
- **Enhanced User Messaging**: Frontend now shows retry-aware progress messages like "If connection issues occur, automatic retries will be attempted..." and specific error messages mentioning retry attempts and fallback methods
- **Chunked Analysis Architecture**: Implements focused analysis on indicator groups (core_trend and volume_momentum), followed by synthesis call that combines partial analyses into final recommendation. Each chunk uses smaller payloads (1500 vs 4096 tokens) to reduce SSL failure risk
- **Connection Error Classification**: Detects and handles SSL, connection, timeout, network, handshake, broken pipe, and connection reset errors with appropriate retry logic and user messaging
- **Maximum Brain SSL Connection Issue Partially Resolved**: Replaced `scipy.signal.find_peaks` with pure pandas/numpy peak detection to eliminate external network dependencies during indicator calculation. However, SSL connection errors still persist during OpenAI API calls - now mitigated with retry and fallback systems
- **Graceful Indicator Handling Implemented**: Added production-grade resilience system with priority-based indicator processing (10 critical + 25 optional indicators), individual error isolation, payload size optimization, and comprehensive success/failure tracking
- **Enhanced Debugging System**: Implemented comprehensive indicator analysis logging that categorizes the 12 failed indicators into: zero values, missing columns, optional limit reached, and calculation errors. System now provides detailed breakdowns showing which 23 of 35 indicators succeeded and exactly why others failed
- **GPT-5 Model Upgrade Attempted**: GPT-5 not yet available in OpenAI API - falls back to optimized GPT-4o with enhanced parameters for Maximum Brain (temperature=0.1, max_tokens=4096) vs standard analysis (temperature=0.3, max_tokens=2048)
- **API Retry Logic**: Implemented exponential backoff retry system for OpenAI rate limiting (HTTP 429) with 3 automatic retries and 1s/2s/4s delays
- **Payload Optimization**: Smart filtering system excludes zero values and limits optional indicators to prevent API timeouts, with detailed payload size monitoring
- **Income Analysis Override Bug Fixed**: System now respects user choice - if income analysis checkbox is not checked, traditional analysis is performed regardless of ticker type
- **I/O Error Resilience System**: Implemented robust error handling for yfinance I/O errors (Errno 5) that occur when reading timezone data files. System now uses multiple fallback approaches: 1) period-based data fetching instead of start/end dates to avoid timezone parsing, 2) reduced timeframe fallback (1 year vs 2 years), 3) graceful degradation with empty info objects. Provides clear user messaging distinguishing I/O errors from ticker validation errors
- **Enhanced SSL Timeout Handling**: Added comprehensive timeout configuration to OpenAI client (60s global, 45s per request) to prevent worker timeouts during SSL handshake delays. Enhanced retryable error detection to include "worker timeout" and "systemexit" errors. Improved error categorization for better user messaging during connection issues
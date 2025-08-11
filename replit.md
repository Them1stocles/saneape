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

### August 11, 2025 - Critical Bug Fixes for Income Analysis and Maximum Brain Debugging
- **Income Analysis Override Bug Fixed**: Removed automatic enabling of income analysis for yield ETFs when users don't request it. System now respects user choice - if income analysis checkbox is not checked, traditional analysis is performed regardless of ticker type (ULTY, MSTY, etc.)
- **Maximum Brain Error Logging Enhanced**: Added comprehensive debugging logging to identify HTTP 500 error causes, including detailed tracebacks, prompt length tracking, indicator counts, and step-by-step analysis logging for technical indicator calculation, data summarization, and AI analysis phases
- **User Choice Respected**: Changed logic from auto-overriding user preference to informational logging only when yield ETFs are detected
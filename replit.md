# SaneApe.com - AI Stock Analysis Platform

## Overview

SaneApe.com is a Flask-based web application that provides AI-powered stock technical analysis. Users can enter a stock ticker symbol and receive an AI-generated recommendation on whether to buy the stock based on historical data and technical indicators. The application uses OpenAI's GPT API for analysis and implements rate limiting to control usage.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Single-page application** using HTML5, CSS3, and vanilla JavaScript
- **Bootstrap 5** for responsive UI components and mobile-first design
- **Feather Icons** for consistent iconography
- **Progressive enhancement** approach with graceful error handling
- Client-side form validation with real-time feedback

### Backend Architecture
- **Flask** web framework with SQLAlchemy ORM
- **Modular design** with separated concerns:
  - `app.py`: Application factory and configuration
  - `routes.py`: Request handling and API endpoints
  - `models.py`: Database models
  - `stock_analyzer.py`: Core analysis logic
  - `rate_limiter.py`: Rate limiting functionality
- **SQLite database** for development with PostgreSQL-ready configuration

### Database Design
Two main models:
- **RateLimit**: Tracks IP-based request limits per day
- **StockAnalysis**: Stores analysis results for future reference

## Key Components

### Stock Analysis Engine
- **yfinance integration** for fetching 2 years of historical stock data
- **Technical indicators calculation** including moving averages (SMA, EMA), RSI, MACD
- **OpenAI GPT-4.1 integration** for AI-powered analysis and recommendations
- **Maximum Brain Analysis** with 35+ technical indicators for comprehensive analysis
- **Data summarization** to optimize API calls and stay within token limits

### Rate Limiting System
- **IP-based limiting** allowing 2 standard requests per day per IP address
- **Maximum Brain limiting** allowing 1 comprehensive analysis per day per IP address
- **Database persistence** to maintain limits across server restarts
- **Graceful error handling** with user-friendly messaging

### Security Features
- **Environment-based configuration** for sensitive data (API keys, database URLs)
- **Input validation** for ticker symbols (letters only, max 5 characters)
- **ProxyFix middleware** for proper IP detection behind reverse proxies
- **SQL injection protection** through SQLAlchemy ORM

## Data Flow

1. **User Input**: User enters stock ticker via web form
2. **Validation**: Client-side and server-side validation of ticker format
3. **Rate Limiting**: Check if IP address has remaining daily requests
4. **Data Fetching**: Retrieve 2 years of historical stock data via yfinance
5. **Technical Analysis**: Calculate various technical indicators
6. **AI Analysis**: Send summarized data to OpenAI GPT-4.1 for analysis
7. **Response Processing**: Parse AI recommendation and confidence level
8. **Data Storage**: Store analysis results in database
9. **User Display**: Present recommendation with detailed breakdown

## External Dependencies

### APIs and Services
- **OpenAI GPT-4.1 API**: For AI-powered stock analysis and recommendations
- **Yahoo Finance (yfinance)**: For historical stock data retrieval

### Python Packages
- **Flask**: Web framework
- **SQLAlchemy**: Database ORM
- **yfinance**: Stock data API wrapper
- **pandas/numpy**: Data manipulation and analysis
- **openai**: OpenAI API client

### Frontend Libraries
- **Bootstrap 5**: CSS framework for responsive design
- **Feather Icons**: Icon library for consistent UI elements

## Deployment Strategy

### Environment Configuration
- **Development**: SQLite database with debug mode enabled
- **Production**: PostgreSQL-ready with environment variable configuration
- **Scalability considerations**: Database connection pooling and session management

### Security Considerations
- API keys managed through environment variables
- Rate limiting to prevent abuse
- Input sanitization and validation
- Secure session management with configurable secret keys

### Future Scalability
- **Architecture prepared for**:
  - User account system implementation
  - Paid subscription tiers
  - Telegram bot integration
  - Horizontal scaling with external database
  - Caching layer for improved performance

### Monitoring and Logging
- **Comprehensive logging** for debugging and monitoring
- **Error tracking** for API failures and data fetching issues
- **Rate limit monitoring** for usage analytics

## Recent Changes: Latest modifications with dates

### July 27, 2025 - Production-Grade Rate Limiting Enhancement
- **Database Schema**: Added SystemLimits, AnalysisCache, and SecurityLog models for comprehensive tracking
- **Cost Management**: Implemented CostManager with $25 configurable daily spend limits and OpenAI token estimation
- **6-Hour Caching**: Added CacheManager to prevent duplicate API calls and reduce costs
- **Security Monitoring**: Implemented SecurityMonitor for suspicious activity detection and threat logging
- **Enhanced Rate Limiter**: Upgraded with multi-layer protection including global cost limits, cache checking, and security validation
- **Admin Dashboard**: Created comprehensive monitoring interface at /admin with real-time metrics and emergency controls
- **Dynamic Frontend**: Enhanced user interface with real-time remaining request display and intelligent button state management
- **Error Handling**: Improved to deny requests during database errors instead of allowing them (security-first approach)
- **API Endpoints**: Added admin controls for emergency stop, limit updates, and system monitoring
- **Recently Analyzed Feature**: Fully implemented with clickable ticker buttons showing cached results without rate limit usage
- **Real-Time Price Updates**: Cached analyses now fetch current stock prices via yfinance, eliminating "NaN" price display issues
- **Badge Overflow Fix**: Enhanced CSS for responsive technical analysis badge layout preventing overflow on mobile devices

### July 27, 2025 - Production-Grade Social Sharing Implementation
- **Brain Favicon**: Created custom SVG brain icon with professional blue gradient for browser tabs and bookmarks
- **Open Graph Meta Tags**: Implemented comprehensive social media metadata using hero ape image for Twitter/Facebook sharing
- **Individual Share Pages**: Built production-grade shareable URLs `/share/AAPL` and `/share/AAPL/brain` for specific analysis results
- **Twitter Integration**: Added native Twitter sharing with custom text, analysis recommendations, and clean URLs
- **Facebook Sharing**: Implemented Facebook sharing functionality with proper Open Graph metadata
- **Share Button UI**: Integrated Twitter, Facebook, and copy-link buttons into main results display with hover animations
- **Expired Analysis Handling**: Created dedicated expired page template with clear re-analysis call-to-action
- **Dynamic Social Content**: Generated contextual social media titles and descriptions based on analysis results
- **Real-Time Price Integration**: Share pages fetch current stock prices to display live data alongside cached analysis
- **Production Security**: Added ticker validation, proper error handling, and noindex meta tags for share pages
- **Mobile Optimization**: Enhanced responsive design for share functionality across all device sizes
- **Professional UX**: Implemented smooth animations, copy-to-clipboard feedback, and consistent branding throughout

### July 27, 2025 - Critical Share System Bug Fixes
- **Smart Redirect Logic**: Fixed "Analysis Expired" errors by implementing intelligent fallback when share URLs don't match analysis type (Standard vs Maximum Brain)
- **Badge Color Fix**: Corrected "Yes, buy!" recommendation badges to display green (bg-success) instead of red by improving template logic
- **Technical Analysis Display**: Added comprehensive technical analysis details to shared pages with proper badge formatting and mobile responsive design
- **URL Generation Consistency**: Updated JavaScript share functions to use query parameter format (?brain=true) matching backend implementation
- **Template Error Resolution**: Removed references to non-existent created_at field preventing template rendering errors
- **Production Testing**: Verified all share URLs work correctly with proper badge colors and complete technical analysis data

### July 27, 2025 - Comprehensive Google Analytics Integration
- **Universal Tracking**: Added Google Analytics (G-3M1MP9NSGT) to all templates including index.html, share.html, and share_expired.html
- **Event Tracking**: Implemented comprehensive custom event tracking for all key user interactions:
  - `stock_analysis_start` and `stock_analysis_complete` with ticker, analysis type, and results
  - `stock_analysis_error` with error types and messages for debugging
  - `share` events for Twitter, Facebook, and copy-link actions with analysis context
  - `recent_analysis_click` for "Recently Analyzed" ticker button interactions
  - `cached_analysis_load` for cached result views
  - `maximum_brain_toggle` for UI interaction tracking
  - `expired_analysis_reanalyze` and `expired_analysis_home` for conversion tracking
- **Share Page Analytics**: Added social media sharing event tracking directly on shared analysis pages
- **Production-Ready Metrics**: All events include proper categorization, labels, and custom parameters for detailed analytics reporting

### July 27, 2025 - Production-Ready Admin Security & API Tracking
- **Comprehensive Admin Protection**: Implemented password-protected admin system (password: "Fluent1!")
- **Professional Login Interface**: Created secure admin login page with 8-hour session timeout and proper error handling
- **API Call Tracking Fixed**: Added missing `cost_manager.record_api_call()` to properly track OpenAI usage and costs
- **Session Management**: Permanent sessions with automatic expiration and logout functionality
- **Security Authentication**: All admin API endpoints require authentication - dashboard access, emergency controls, budget management, and IP resets
- **Real-Time Monitoring**: Admin dashboard now displays accurate API call counts, daily costs, and system metrics
- **Production Testing**: Verified all components working correctly - rate limiting, cost tracking, caching, and social sharing

### July 27, 2025 - Twitter Handle & Brand Message Update
- **Twitter Handle Updated**: Changed all social sharing from @SaneApe_com to @saneape to match actual Twitter profile
- **Brand Messaging Enhanced**: Added signature tagline "Ape on data, not vibes - a sanity check for late night traders & hopium addicts" to Twitter shares
- **Social Media Consistency**: Updated both main app sharing and individual share page Twitter functionality
- **Brand Identity**: Reinforced core value proposition of data-driven analysis over emotional trading decisions

### July 27, 2025 - Future Features Roadmap Enhancement
- **Viral Feature Expansion**: Added comprehensive future feature list to "Coming Soon If We Go Viral" section
- **New Planned Features**: X ticker sentiment via Grok, Telegram bot requests, daily ticker updates, and emergency notifications
- **User Engagement**: Enhanced feature roadmap to build anticipation and encourage sharing for platform growth
- **Strategic Positioning**: Positioned advanced features as viral milestone rewards to incentivize user promotion

### July 27, 2025 - CRITICAL: Income-Focused Analysis Payment Frequency Logic Fixed
- **Payment Frequency Detection**: Fixed critical flaw in yield calculation logic that incorrectly assumed all ETFs pay monthly
- **Real Data Analysis**: Now analyzes actual dividend payment intervals from 12 months of historical data to detect weekly/monthly/quarterly patterns
- **Accurate Yield Calculations**: Properly calculates annualized yields based on actual payment frequency (ULTY=weekly 52x/year, YieldMax=monthly 12x/year)
- **Smart Fallbacks**: Uses known patterns for specific tickers when dividend data unavailable (ULTY ~45%, YieldMax ~25%)
- **Enhanced UI Display**: Shows payment frequency, payments per year, and actual dividend count in income analysis section
- **Comprehensive Integration**: Full backend and frontend integration with auto-detection of yield ETFs and specialized income metrics
- **Production Ready**: Income analysis now provides accurate effective returns accounting for NAV decay, expenses, and tax implications

### July 27, 2025 - MAJOR: Bulletproof Maximum Brain Analysis System Complete
- **Critical Fix**: Resolved all stockstats library parsing errors that were causing technical indicators to return zero values
- **Hybrid Architecture**: Implemented bulletproof dual-system approach using stockstats when available, pure pandas calculations as failsafe
- **35 Indicators Working**: All comprehensive technical indicators now calculate properly with real values instead of zeros
- **Error Elimination**: Fixed "Invalid number of return arguments after parsing column name" errors completely
- **Production Ready**: Maximum Brain Analysis now provides genuine institutional-grade technical analysis with full reliability
- **Pandas Modernization**: Updated deprecated `fillna(method='ffill')` to modern `ffill()` syntax
- **Failsafe Error Handling**: Added comprehensive error handling to prevent analysis failures and ensure data integrity
- **JSON Format Fix**: Added missing JSON format specification to Maximum Brain Analysis prompt, resolving "No recommendation" parsing errors
- **Rate Limit Enhancement**: Updated limits from 2 standard/1 Maximum Brain to 6 standard/2 Maximum Brain requests per day
- **UI Enhancement**: Added glowing yellow pulse animation to Maximum Brain Analysis option for better visibility and engagement
- **Testing Verified**: Successfully tested with TSLA - complete analysis generation, proper caching, and cost tracking working perfectly
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
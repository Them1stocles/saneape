"""
Analysis Cache Management System with 6-hour TTL.
Production-grade implementation for reducing duplicate OpenAI API calls.
"""

from extensions import db
from models import AnalysisCache
from datetime import datetime, timedelta
import json
import logging

class CacheManager:
    """Manages analysis result caching with 6-hour TTL"""
    
    CACHE_DURATION_HOURS = 6
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def _generate_cache_key(self, ticker, maximum_brain=False):
        """Generate consistent cache key for ticker and analysis type"""
        return f"{ticker.upper()}_{maximum_brain}"
    
    def get_cached_analysis(self, ticker, maximum_brain=False):
        """Retrieve cached analysis if available and not expired"""
        try:
            cache_key = self._generate_cache_key(ticker, maximum_brain)
            
            # Find non-expired cache entry
            stmt = db.select(AnalysisCache).filter(
                AnalysisCache.ticker_symbol == ticker.upper(),
                AnalysisCache.maximum_brain.is_(maximum_brain),
                AnalysisCache.cache_expiry > datetime.utcnow()
            )
            cached = db.session.execute(stmt).scalars().first()
            
            if cached:
                self.logger.info(f"Cache hit for {cache_key}")
                try:
                    analysis_data = json.loads(cached.analysis_data)
                    return analysis_data
                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON in cache for {cache_key}: {str(e)}")
                    # Delete corrupted cache entry
                    db.session.delete(cached)
                    db.session.commit()
                    return None
            
            self.logger.info(f"Cache miss for {cache_key}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving cached analysis: {str(e)}")
            return None
    
    def store_analysis(self, ticker, analysis_result, maximum_brain=False):
        """Store analysis result in cache with 6-hour expiry"""
        try:
            if not analysis_result or not analysis_result.get('success'):
                self.logger.warning(f"Not caching failed analysis for {ticker}")
                return False
            
            # Remove any existing cache for this ticker/type combination
            stmt = db.select(AnalysisCache).filter(
                AnalysisCache.ticker_symbol == ticker.upper(),
                AnalysisCache.maximum_brain.is_(maximum_brain)
            )
            existing = db.session.execute(stmt).scalars().all()
            
            for cache_entry in existing:
                db.session.delete(cache_entry)
            
            # Create new cache entry
            cache_entry = AnalysisCache()
            cache_entry.ticker_symbol = ticker.upper()
            cache_entry.maximum_brain = maximum_brain
            cache_entry.analysis_data = json.dumps(analysis_result)
            cache_entry.created_at = datetime.utcnow()
            cache_entry.cache_expiry = datetime.utcnow() + timedelta(hours=self.CACHE_DURATION_HOURS)
            
            db.session.add(cache_entry)
            db.session.commit()
            
            cache_key = self._generate_cache_key(ticker, maximum_brain)
            self.logger.info(f"Cached analysis for {cache_key} until {cache_entry.cache_expiry}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing cache for {ticker}: {e}")
            db.session.rollback()
            return False
    
    def is_analysis_cached(self, ticker, maximum_brain=False):
        """Check if analysis is cached without retrieving the data"""
        try:
            stmt = db.select(AnalysisCache).filter(
                AnalysisCache.ticker_symbol == ticker.upper(),
                AnalysisCache.maximum_brain.is_(maximum_brain),
                AnalysisCache.cache_expiry > datetime.utcnow()
            )
            cached = db.session.execute(stmt).scalars().first()
            
            return cached is not None
            
        except Exception as e:
            self.logger.error(f"Error checking cache status: {str(e)}")
            return False
    
    def get_cache_info(self, ticker, maximum_brain=False):
        """Get cache information including expiry time"""
        try:
            stmt = db.select(AnalysisCache).filter(
                AnalysisCache.ticker_symbol == ticker.upper(),
                AnalysisCache.maximum_brain.is_(maximum_brain)
            )
            cached = db.session.execute(stmt).scalars().first()
            
            if not cached:
                return None
            
            return {
                'ticker': cached.ticker_symbol,
                'maximum_brain': cached.maximum_brain,
                'created_at': cached.created_at.isoformat(),
                'cache_expiry': cached.cache_expiry.isoformat(),
                'is_expired': cached.cache_expiry <= datetime.utcnow(), # Corrected from cached.is_expired
                'minutes_remaining': max(0, int((cached.cache_expiry - datetime.utcnow()).total_seconds() / 60))
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache info: {str(e)}")
            return None
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        try:
            stmt = db.delete(AnalysisCache).where(AnalysisCache.cache_expiry < datetime.utcnow())
            result = db.session.execute(stmt)
            db.session.commit()
            return result.rowcount
        except Exception as e:
            self.logger.error(f"Error cleaning up cache: {e}")
            return 0
    
    def clear_cache_for_ticker(self, ticker):
        """Clear all cache entries for a specific ticker"""
        try:
            stmt = db.delete(AnalysisCache).filter(
                AnalysisCache.ticker_symbol == ticker.upper()
            )
            result = db.session.execute(stmt)
            db.session.commit()
            
            self.logger.info(f"Cleared {result.rowcount} cache entries for {ticker}")
            return result.rowcount
            
        except Exception as e:
            self.logger.error(f"Error clearing cache for {ticker}: {str(e)}")
            db.session.rollback()
            return 0
    
    def get_cache_stats(self):
        """Get overall cache statistics"""
        try:
            # Count total entries
            stmt_total = db.select(db.func.count(AnalysisCache.id))
            total_entries = db.session.execute(stmt_total).scalar() or 0
            
            # Count active entries
            stmt_active = db.select(db.func.count(AnalysisCache.id)).where(
                AnalysisCache.cache_expiry > datetime.utcnow()
            )
            active_entries = db.session.execute(stmt_active).scalar() or 0
            
            expired_entries = total_entries - active_entries
            
            return {
                'total_entries': total_entries,
                'active_entries': active_entries,
                'expired_entries': expired_entries,
                'cache_duration_hours': self.CACHE_DURATION_HOURS
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {str(e)}")
            return None
    
    def invalidate_all_cache(self):
        """Emergency function to clear all cache entries"""
        try:
            stmt = db.delete(AnalysisCache)
            result = db.session.execute(stmt)
            db.session.commit()
            
            self.logger.warning(f"Emergency cache invalidation: cleared {result.rowcount} entries")
            return result.rowcount
            
        except Exception as e:
            self.logger.error(f"Error invalidating all cache: {str(e)}")
            db.session.rollback()
            return 0
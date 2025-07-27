"""
Security Monitoring System for tracking suspicious activity and rate limit violations.
Production-grade implementation with comprehensive logging and threat detection.
"""

from app import db
from models import SecurityLog
from datetime import datetime, date, timedelta
import logging

class SecurityMonitor:
    """Monitors and logs security events and suspicious activity"""
    
    # Event types
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    REPEATED_ATTEMPTS = "repeated_attempts"
    INVALID_INPUT = "invalid_input"
    COST_LIMIT_HIT = "cost_limit_hit"
    EMERGENCY_STOP = "emergency_stop"
    
    # Thresholds for suspicious activity
    MAX_ATTEMPTS_PER_HOUR = 10
    MAX_ATTEMPTS_PER_DAY = 50
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def log_security_event(self, ip_address, event_type, details=None):
        """Log a security event and update counters"""
        try:
            today = date.today()
            
            # Get existing log for this IP and event type today
            security_log = SecurityLog.query.filter_by(
                ip_address=ip_address,
                event_type=event_type,
                date_created=today
            ).first()
            
            if security_log:
                # Update existing log
                security_log.event_count += 1
                security_log.last_attempt = datetime.utcnow()
                if details:
                    security_log.event_details = details
            else:
                # Create new security log
                security_log = SecurityLog()
                security_log.ip_address = ip_address
                security_log.event_type = event_type
                security_log.event_count = 1
                security_log.event_details = details
                security_log.last_attempt = datetime.utcnow()
                security_log.date_created = today
                db.session.add(security_log)
            
            db.session.commit()
            
            self.logger.warning(f"Security event: {event_type} from {ip_address} (count: {security_log.event_count})")
            
            # Check for suspicious patterns
            self._check_suspicious_activity(ip_address, event_type, security_log.event_count)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging security event: {str(e)}")
            db.session.rollback()
            return False
    
    def _check_suspicious_activity(self, ip_address, event_type, count):
        """Check if activity patterns indicate suspicious behavior"""
        try:
            # Check for excessive attempts
            if count >= self.MAX_ATTEMPTS_PER_HOUR:
                self.logger.critical(f"SUSPICIOUS: {ip_address} has {count} {event_type} events today")
                
                # Log the suspicious activity as a separate event
                self.log_security_event(
                    ip_address, 
                    self.REPEATED_ATTEMPTS, 
                    f"{count} {event_type} events in one day"
                )
            
            # Check total events across all types for this IP today
            total_events = db.session.query(db.func.sum(SecurityLog.event_count)).filter_by(
                ip_address=ip_address,
                date_created=date.today()
            ).scalar() or 0
            
            if total_events >= self.MAX_ATTEMPTS_PER_DAY:
                self.logger.critical(f"THREAT DETECTED: {ip_address} has {total_events} total security events today")
            
        except Exception as e:
            self.logger.error(f"Error checking suspicious activity: {str(e)}")
    
    def is_ip_suspicious(self, ip_address):
        """Check if an IP address shows suspicious patterns"""
        try:
            today = date.today()
            
            # Get total events for this IP today
            total_events = db.session.query(db.func.sum(SecurityLog.event_count)).filter_by(
                ip_address=ip_address,
                date_created=today
            ).scalar() or 0
            
            # Check for repeated attempts in the last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_events = SecurityLog.query.filter(
                SecurityLog.ip_address == ip_address,
                SecurityLog.last_attempt >= one_hour_ago
            ).count()
            
            is_suspicious = (
                total_events >= self.MAX_ATTEMPTS_PER_DAY or 
                recent_events >= self.MAX_ATTEMPTS_PER_HOUR
            )
            
            if is_suspicious:
                self.logger.warning(f"IP {ip_address} flagged as suspicious: {total_events} daily events, {recent_events} recent events")
            
            return is_suspicious
            
        except Exception as e:
            self.logger.error(f"Error checking if IP is suspicious: {str(e)}")
            return False
    
    def get_ip_security_summary(self, ip_address):
        """Get security summary for a specific IP address"""
        try:
            today = date.today()
            
            # Get all events for this IP today
            events = SecurityLog.query.filter_by(
                ip_address=ip_address,
                date_created=today
            ).all()
            
            summary = {
                'ip_address': ip_address,
                'date': today.isoformat(),
                'total_events': sum(event.event_count for event in events),
                'event_types': {},
                'is_suspicious': False,
                'last_activity': None
            }
            
            for event in events:
                summary['event_types'][event.event_type] = {
                    'count': event.event_count,
                    'last_attempt': event.last_attempt.isoformat(),
                    'details': event.event_details
                }
                
                if not summary['last_activity'] or event.last_attempt > datetime.fromisoformat(summary['last_activity']):
                    summary['last_activity'] = event.last_attempt.isoformat()
            
            summary['is_suspicious'] = self.is_ip_suspicious(ip_address)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting IP security summary: {str(e)}")
            return None
    
    def get_daily_security_report(self, target_date=None):
        """Get comprehensive security report for a specific date"""
        try:
            if target_date is None:
                target_date = date.today()
            
            events = SecurityLog.query.filter_by(date_created=target_date).all()
            
            report = {
                'date': target_date.isoformat(),
                'total_events': sum(event.event_count for event in events),
                'unique_ips': len(set(event.ip_address for event in events)),
                'event_breakdown': {},
                'suspicious_ips': [],
                'top_offenders': []
            }
            
            # Event breakdown by type
            for event in events:
                if event.event_type not in report['event_breakdown']:
                    report['event_breakdown'][event.event_type] = 0
                report['event_breakdown'][event.event_type] += event.event_count
            
            # Get suspicious IPs
            ip_counts = {}
            for event in events:
                if event.ip_address not in ip_counts:
                    ip_counts[event.ip_address] = 0
                ip_counts[event.ip_address] += event.event_count
            
            # Find suspicious IPs and top offenders
            for ip, count in ip_counts.items():
                if count >= self.MAX_ATTEMPTS_PER_HOUR:
                    report['suspicious_ips'].append({'ip': ip, 'events': count})
            
            # Top 10 offenders
            report['top_offenders'] = sorted(
                [{'ip': ip, 'events': count} for ip, count in ip_counts.items()],
                key=lambda x: x['events'],
                reverse=True
            )[:10]
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating daily security report: {str(e)}")
            return None
    
    def cleanup_old_logs(self, days_to_keep=7):
        """Clean up old security logs"""
        try:
            cutoff_date = date.today() - timedelta(days=days_to_keep)
            deleted = SecurityLog.query.filter(SecurityLog.date_created < cutoff_date).delete()
            db.session.commit()
            
            if deleted > 0:
                self.logger.info(f"Cleaned up {deleted} old security log entries")
            
            return deleted
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old security logs: {str(e)}")
            db.session.rollback()
            return 0
    
    def block_suspicious_ip(self, ip_address, reason="Suspicious activity detected"):
        """Log a blocking event for a suspicious IP"""
        try:
            self.log_security_event(ip_address, "ip_blocked", reason)
            self.logger.critical(f"IP {ip_address} blocked: {reason}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error blocking IP {ip_address}: {str(e)}")
            return False
    
    def get_security_metrics(self):
        """Get overall security metrics"""
        try:
            today = date.today()
            last_7_days = today - timedelta(days=7)
            
            # Today's metrics
            today_events = db.session.query(db.func.sum(SecurityLog.event_count)).filter_by(
                date_created=today
            ).scalar() or 0
            
            today_ips = db.session.query(db.func.count(db.func.distinct(SecurityLog.ip_address))).filter_by(
                date_created=today
            ).scalar() or 0
            
            # Last 7 days metrics
            week_events = db.session.query(db.func.sum(SecurityLog.event_count)).filter(
                SecurityLog.date_created >= last_7_days
            ).scalar() or 0
            
            week_ips = db.session.query(db.func.count(db.func.distinct(SecurityLog.ip_address))).filter(
                SecurityLog.date_created >= last_7_days
            ).scalar() or 0
            
            return {
                'today': {
                    'events': today_events,
                    'unique_ips': today_ips
                },
                'last_7_days': {
                    'events': week_events,
                    'unique_ips': week_ips
                },
                'thresholds': {
                    'max_attempts_per_hour': self.MAX_ATTEMPTS_PER_HOUR,
                    'max_attempts_per_day': self.MAX_ATTEMPTS_PER_DAY
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting security metrics: {str(e)}")
            return None
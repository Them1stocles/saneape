"""
Production-grade monitoring and alerting system for user accounts and payments.
Tracks critical metrics, payment failures, and system health.
"""

import os
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from collections import deque, defaultdict

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """Types of metrics to track"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class Alert:
    """Alert data structure"""
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None

@dataclass
class Metric:
    """Metric data structure"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    tags: Dict[str, str]

class PaymentMonitor:
    """Specialized monitoring for payment-related events"""
    
    def __init__(self):
        self.payment_failures = deque(maxlen=1000)  # Keep last 1000 failures
        self.payment_success_rate = deque(maxlen=100)  # Track success rate over last 100 payments
        self.stripe_webhook_failures = deque(maxlen=500)
        self.suspicious_activities = deque(maxlen=200)
        
    def record_payment_attempt(self, user_id: str, amount: float, success: bool, failure_reason: str = None):
        """Record a payment attempt for monitoring"""
        self.payment_success_rate.append(success)
        
        if not success:
            failure_data = {
                'user_id': user_id,
                'amount': amount,
                'failure_reason': failure_reason,
                'timestamp': datetime.utcnow(),
                'retry_count': 0
            }
            self.payment_failures.append(failure_data)
            
            # Alert on high failure rate
            recent_failures = sum(1 for x in list(self.payment_success_rate)[-20:] if not x)
            if recent_failures >= 5:  # 5+ failures in last 20 attempts
                MonitoringManager().create_alert(
                    AlertSeverity.WARNING,
                    "High Payment Failure Rate",
                    f"5+ payment failures in last 20 attempts. Recent failure: {failure_reason}",
                    {"user_id": user_id, "failure_reason": failure_reason}
                )
    
    def record_webhook_failure(self, event_type: str, stripe_event_id: str, error: str):
        """Record Stripe webhook processing failure"""
        failure_data = {
            'event_type': event_type,
            'stripe_event_id': stripe_event_id,
            'error': error,
            'timestamp': datetime.utcnow()
        }
        self.stripe_webhook_failures.append(failure_data)
        
        # Alert on webhook failures
        MonitoringManager().create_alert(
            AlertSeverity.ERROR,
            "Stripe Webhook Failure",
            f"Failed to process {event_type} webhook: {error}",
            {"event_id": stripe_event_id, "event_type": event_type}
        )
    
    def record_suspicious_activity(self, user_id: str, activity_type: str, details: Dict[str, Any]):
        """Record suspicious payment activity"""
        activity_data = {
            'user_id': user_id,
            'activity_type': activity_type,
            'details': details,
            'timestamp': datetime.utcnow()
        }
        self.suspicious_activities.append(activity_data)
        
        # Alert on suspicious patterns
        if activity_type in ['rapid_purchases', 'unusual_payment_method', 'high_value_transaction']:
            MonitoringManager().create_alert(
                AlertSeverity.WARNING,
                "Suspicious Payment Activity",
                f"Detected {activity_type} for user {user_id}",
                {"user_id": user_id, "activity_type": activity_type, "details": details}
            )
    
    def get_payment_health_metrics(self) -> Dict[str, Any]:
        """Get payment system health metrics"""
        if not self.payment_success_rate:
            return {"success_rate": 0, "total_attempts": 0, "recent_failures": 0}
            
        success_rate = sum(self.payment_success_rate) / len(self.payment_success_rate)
        recent_failures = len([f for f in self.payment_failures if f['timestamp'] > datetime.utcnow() - timedelta(hours=24)])
        
        return {
            "success_rate": round(success_rate * 100, 2),
            "total_attempts": len(self.payment_success_rate),
            "recent_failures": recent_failures,
            "webhook_failures_24h": len([f for f in self.stripe_webhook_failures if f['timestamp'] > datetime.utcnow() - timedelta(hours=24)]),
            "suspicious_activities_24h": len([a for a in self.suspicious_activities if a['timestamp'] > datetime.utcnow() - timedelta(hours=24)])
        }

class SystemMonitor:
    """System-wide performance and health monitoring"""
    
    def __init__(self):
        self.metrics = defaultdict(deque)  # metric_name -> deque of values
        self.error_counts = defaultdict(int)
        self.performance_timers = {}
        
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a metric value"""
        if tags is None:
            tags = {}
            
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.GAUGE,
            timestamp=datetime.utcnow(),
            tags=tags
        )
        
        # Keep last 1000 values for each metric
        self.metrics[name].append(metric)
        if len(self.metrics[name]) > 1000:
            self.metrics[name].popleft()
    
    def increment_counter(self, name: str, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        current_value = self.get_latest_metric_value(name, 0)
        self.record_metric(name, current_value + 1, tags)
    
    def record_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """Record an error occurrence"""
        self.error_counts[error_type] += 1
        
        # Alert on high error rates
        if self.error_counts[error_type] % 10 == 0:  # Every 10th occurrence
            MonitoringManager().create_alert(
                AlertSeverity.ERROR,
                f"High {error_type} Error Rate",
                f"10+ occurrences of {error_type}: {error_message}",
                context or {}
            )
    
    def start_timer(self, name: str) -> str:
        """Start a performance timer"""
        timer_id = f"{name}_{int(time.time() * 1000)}"
        self.performance_timers[timer_id] = time.time()
        return timer_id
    
    def end_timer(self, timer_id: str, tags: Dict[str, str] = None):
        """End a performance timer and record duration"""
        if timer_id in self.performance_timers:
            duration = time.time() - self.performance_timers[timer_id]
            metric_name = timer_id.split('_')[0] + '_duration'
            self.record_metric(metric_name, duration, tags)
            del self.performance_timers[timer_id]
            return duration
        return None
    
    def get_latest_metric_value(self, name: str, default: float = 0.0) -> float:
        """Get the latest value for a metric"""
        if name in self.metrics and self.metrics[name]:
            return self.metrics[name][-1].value
        return default
    
    def get_metric_summary(self, name: str, hours: int = 24) -> Dict[str, float]:
        """Get summary statistics for a metric over specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_values = [
            m.value for m in self.metrics[name] 
            if m.timestamp > cutoff_time
        ]
        
        if not recent_values:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}
            
        return {
            "count": len(recent_values),
            "avg": sum(recent_values) / len(recent_values),
            "min": min(recent_values),
            "max": max(recent_values)
        }

class MonitoringManager:
    """Central monitoring manager coordinating all monitoring activities"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern for global monitoring"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.payment_monitor = PaymentMonitor()
            self.system_monitor = SystemMonitor()
            self.alerts = deque(maxlen=1000)
            self.alert_handlers = []
            self.initialized = True
            logger.info("Monitoring system initialized")
    
    def create_alert(self, severity: AlertSeverity, title: str, message: str, metadata: Dict[str, Any] = None):
        """Create and process a new alert"""
        alert = Alert(
            severity=severity,
            title=title,
            message=message,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        self.alerts.append(alert)
        logger.log(
            logging.CRITICAL if severity == AlertSeverity.CRITICAL else
            logging.ERROR if severity == AlertSeverity.ERROR else
            logging.WARNING if severity == AlertSeverity.WARNING else
            logging.INFO,
            f"ALERT [{severity.value.upper()}] {title}: {message}"
        )
        
        # Trigger alert handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    def resolve_alert(self, alert_title: str):
        """Mark alerts as resolved"""
        for alert in self.alerts:
            if alert.title == alert_title and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                logger.info(f"Alert resolved: {alert_title}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all unresolved alerts"""
        return [alert for alert in self.alerts if not alert.resolved]
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        payment_health = self.payment_monitor.get_payment_health_metrics()
        active_alerts = len(self.get_active_alerts())
        critical_alerts = len([a for a in self.get_active_alerts() if a.severity == AlertSeverity.CRITICAL])
        
        # Calculate overall health score (0-100)
        health_score = 100
        if payment_health["success_rate"] < 95:
            health_score -= 20
        if active_alerts > 5:
            health_score -= 15
        if critical_alerts > 0:
            health_score -= 30
        
        health_status = "healthy" if health_score >= 80 else "degraded" if health_score >= 60 else "unhealthy"
        
        return {
            "overall_health": health_status,
            "health_score": max(0, health_score),
            "payment_health": payment_health,
            "active_alerts": active_alerts,
            "critical_alerts": critical_alerts,
            "system_uptime": self._get_uptime(),
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def _get_uptime(self) -> str:
        """Get system uptime (placeholder - would use actual start time)"""
        # In production, this would track actual application start time
        return "1d 5h 23m"
    
    def add_alert_handler(self, handler_func):
        """Add custom alert handler function"""
        self.alert_handlers.append(handler_func)
    
    def export_metrics(self, format: str = "json") -> str:
        """Export all metrics in specified format"""
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "system_health": self.get_system_health(),
            "payment_metrics": self.payment_monitor.get_payment_health_metrics(),
            "active_alerts": [asdict(alert) for alert in self.get_active_alerts()],
            "error_counts": dict(self.system_monitor.error_counts)
        }
        
        if format == "json":
            return json.dumps(data, indent=2, default=str)
        else:
            return str(data)

# Global monitoring instance
monitoring = MonitoringManager()

# Convenience functions for common monitoring tasks
def record_payment_failure(user_id: str, amount: float, reason: str):
    """Record a payment failure"""
    monitoring.payment_monitor.record_payment_attempt(user_id, amount, False, reason)

def record_payment_success(user_id: str, amount: float):
    """Record a successful payment"""
    monitoring.payment_monitor.record_payment_attempt(user_id, amount, True)

def record_api_call(endpoint: str, duration: float, status_code: int):
    """Record API call metrics"""
    monitoring.system_monitor.record_metric("api_call_duration", duration, {"endpoint": endpoint})
    monitoring.system_monitor.record_metric("api_call_status", status_code, {"endpoint": endpoint})

def record_user_action(action: str, user_id: str = None):
    """Record user action for analytics"""
    tags = {"action": action}
    if user_id:
        tags["user_id"] = user_id
    monitoring.system_monitor.increment_counter("user_actions", tags)

def create_alert(severity: str, title: str, message: str, metadata: Dict[str, Any] = None):
    """Create an alert with simplified interface"""
    severity_enum = AlertSeverity(severity.lower())
    monitoring.create_alert(severity_enum, title, message, metadata)

# Performance monitoring decorator
def monitor_performance(metric_name: str):
    """Decorator to monitor function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            timer_id = monitoring.system_monitor.start_timer(metric_name)
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                monitoring.system_monitor.record_error(f"{metric_name}_error", str(e))
                raise
            finally:
                monitoring.system_monitor.end_timer(timer_id)
        return wrapper
    return decorator
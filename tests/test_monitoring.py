"""
Unit tests for monitoring and alerting system.
Tests payment monitoring, system metrics, and alert management.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from monitoring import (
    MonitoringManager,
    PaymentMonitor,
    SystemMonitor,
    Alert,
    AlertSeverity,
    MetricType,
    record_payment_failure,
    record_payment_success,
    create_alert,
    monitor_performance
)

class TestPaymentMonitor:
    """Test payment monitoring functionality"""
    
    def test_record_payment_success(self):
        """Test recording successful payment"""
        monitor = PaymentMonitor()
        
        monitor.record_payment_attempt('user123', 5.00, True)
        
        assert len(monitor.payment_success_rate) == 1
        assert monitor.payment_success_rate[0] is True
        assert len(monitor.payment_failures) == 0
    
    def test_record_payment_failure(self):
        """Test recording failed payment"""
        monitor = PaymentMonitor()
        
        monitor.record_payment_attempt('user123', 5.00, False, 'insufficient_funds')
        
        assert len(monitor.payment_success_rate) == 1
        assert monitor.payment_success_rate[0] is False
        assert len(monitor.payment_failures) == 1
        
        failure = monitor.payment_failures[0]
        assert failure['user_id'] == 'user123'
        assert failure['amount'] == 5.00
        assert failure['failure_reason'] == 'insufficient_funds'
    
    @patch('monitoring.MonitoringManager')
    def test_high_failure_rate_alert(self, mock_monitoring):
        """Test alert is created for high failure rate"""
        monitor = PaymentMonitor()
        
        # Record 5 failures in a row
        for i in range(5):
            monitor.record_payment_attempt(f'user{i}', 5.00, False, 'card_declined')
        
        # Should trigger alert on 5th failure
        mock_monitoring.return_value.create_alert.assert_called()
    
    def test_webhook_failure_recording(self):
        """Test recording webhook failures"""
        monitor = PaymentMonitor()
        
        monitor.record_webhook_failure(
            'customer.subscription.created',
            'evt_test123',
            'Invalid signature'
        )
        
        assert len(monitor.stripe_webhook_failures) == 1
        
        failure = monitor.stripe_webhook_failures[0]
        assert failure['event_type'] == 'customer.subscription.created'
        assert failure['stripe_event_id'] == 'evt_test123'
        assert failure['error'] == 'Invalid signature'
    
    def test_suspicious_activity_recording(self):
        """Test recording suspicious payment activity"""
        monitor = PaymentMonitor()
        
        monitor.record_suspicious_activity(
            'user123',
            'rapid_purchases',
            {'purchase_count': 10, 'time_window': '5_minutes'}
        )
        
        assert len(monitor.suspicious_activities) == 1
        
        activity = monitor.suspicious_activities[0]
        assert activity['user_id'] == 'user123'
        assert activity['activity_type'] == 'rapid_purchases'
    
    def test_payment_health_metrics(self):
        """Test payment health metrics calculation"""
        monitor = PaymentMonitor()
        
        # Record mix of successes and failures
        monitor.record_payment_attempt('user1', 5.00, True)
        monitor.record_payment_attempt('user2', 5.00, True)
        monitor.record_payment_attempt('user3', 5.00, False, 'declined')
        monitor.record_payment_attempt('user4', 5.00, True)
        
        metrics = monitor.get_payment_health_metrics()
        
        assert metrics['success_rate'] == 75.0  # 3/4 = 75%
        assert metrics['total_attempts'] == 4
        assert metrics['recent_failures'] >= 0

class TestSystemMonitor:
    """Test system monitoring functionality"""
    
    def test_record_metric(self):
        """Test recording system metrics"""
        monitor = SystemMonitor()
        
        monitor.record_metric('api_response_time', 0.15, {'endpoint': '/analyze'})
        
        assert 'api_response_time' in monitor.metrics
        assert len(monitor.metrics['api_response_time']) == 1
        
        metric = monitor.metrics['api_response_time'][0]
        assert metric.value == 0.15
        assert metric.tags['endpoint'] == '/analyze'
    
    def test_increment_counter(self):
        """Test incrementing counter metrics"""
        monitor = SystemMonitor()
        
        # First increment
        monitor.increment_counter('user_signups')
        assert monitor.get_latest_metric_value('user_signups') == 1
        
        # Second increment
        monitor.increment_counter('user_signups')
        assert monitor.get_latest_metric_value('user_signups') == 2
    
    def test_record_error(self):
        """Test recording errors"""
        monitor = SystemMonitor()
        
        monitor.record_error('database_connection', 'Connection timeout', {'host': 'db.example.com'})
        
        assert monitor.error_counts['database_connection'] == 1
    
    def test_performance_timer(self):
        """Test performance timing functionality"""
        monitor = SystemMonitor()
        
        timer_id = monitor.start_timer('test_operation')
        assert timer_id in monitor.performance_timers
        
        duration = monitor.end_timer(timer_id)
        assert duration is not None
        assert duration >= 0
        assert timer_id not in monitor.performance_timers
    
    def test_metric_summary(self):
        """Test metric summary calculation"""
        monitor = SystemMonitor()
        
        # Record some test metrics
        monitor.record_metric('response_time', 0.1)
        monitor.record_metric('response_time', 0.2)
        monitor.record_metric('response_time', 0.15)
        
        summary = monitor.get_metric_summary('response_time', hours=24)
        
        assert summary['count'] == 3
        assert summary['avg'] == 0.15
        assert summary['min'] == 0.1
        assert summary['max'] == 0.2
    
    def test_metric_summary_empty(self):
        """Test metric summary with no data"""
        monitor = SystemMonitor()
        
        summary = monitor.get_metric_summary('nonexistent_metric')
        
        assert summary['count'] == 0
        assert summary['avg'] == 0
        assert summary['min'] == 0
        assert summary['max'] == 0

class TestMonitoringManager:
    """Test the central monitoring manager"""
    
    def test_singleton_pattern(self):
        """Test monitoring manager is singleton"""
        manager1 = MonitoringManager()
        manager2 = MonitoringManager()
        
        assert manager1 is manager2
    
    def test_create_alert(self):
        """Test creating alerts"""
        manager = MonitoringManager()
        
        manager.create_alert(
            AlertSeverity.WARNING,
            'Test Alert',
            'This is a test alert',
            {'test_key': 'test_value'}
        )
        
        assert len(manager.alerts) == 1
        
        alert = manager.alerts[0]
        assert alert.severity == AlertSeverity.WARNING
        assert alert.title == 'Test Alert'
        assert alert.message == 'This is a test alert'
        assert alert.metadata['test_key'] == 'test_value'
        assert not alert.resolved
    
    def test_resolve_alert(self):
        """Test resolving alerts"""
        manager = MonitoringManager()
        
        manager.create_alert(AlertSeverity.INFO, 'Test Alert', 'Test message')
        manager.resolve_alert('Test Alert')
        
        alerts = list(manager.alerts)
        assert len(alerts) == 1
        assert alerts[0].resolved is True
        assert alerts[0].resolved_at is not None
    
    def test_get_active_alerts(self):
        """Test getting only unresolved alerts"""
        manager = MonitoringManager()
        
        manager.create_alert(AlertSeverity.INFO, 'Active Alert', 'Active')
        manager.create_alert(AlertSeverity.WARNING, 'Resolved Alert', 'Resolved')
        manager.resolve_alert('Resolved Alert')
        
        active_alerts = manager.get_active_alerts()
        
        assert len(active_alerts) == 1
        assert active_alerts[0].title == 'Active Alert'
    
    def test_system_health_calculation(self):
        """Test system health score calculation"""
        manager = MonitoringManager()
        
        # Mock payment health
        with patch.object(manager.payment_monitor, 'get_payment_health_metrics') as mock_payment:
            mock_payment.return_value = {
                'success_rate': 98.0,
                'total_attempts': 100,
                'recent_failures': 2,
                'webhook_failures_24h': 0,
                'suspicious_activities_24h': 0
            }
            
            health = manager.get_system_health()
            
            assert health['overall_health'] == 'healthy'
            assert health['health_score'] >= 80
            assert 'payment_health' in health
            assert 'active_alerts' in health
    
    def test_system_health_degraded(self):
        """Test system health with degraded conditions"""
        manager = MonitoringManager()
        
        # Create multiple alerts to degrade health
        for i in range(6):
            manager.create_alert(AlertSeverity.WARNING, f'Alert {i}', f'Message {i}')
        
        with patch.object(manager.payment_monitor, 'get_payment_health_metrics') as mock_payment:
            mock_payment.return_value = {
                'success_rate': 90.0,  # Below 95% threshold
                'total_attempts': 100,
                'recent_failures': 10,
                'webhook_failures_24h': 0,
                'suspicious_activities_24h': 0
            }
            
            health = manager.get_system_health()
            
            assert health['overall_health'] in ['degraded', 'unhealthy']
            assert health['health_score'] < 80

class TestConvenienceFunctions:
    """Test convenience functions for monitoring"""
    
    @patch('monitoring.monitoring')
    def test_record_payment_failure_function(self, mock_monitoring):
        """Test payment failure recording convenience function"""
        record_payment_failure('user123', 5.00, 'card_declined')
        
        mock_monitoring.payment_monitor.record_payment_attempt.assert_called_once_with(
            'user123', 5.00, False, 'card_declined'
        )
    
    @patch('monitoring.monitoring')
    def test_record_payment_success_function(self, mock_monitoring):
        """Test payment success recording convenience function"""
        record_payment_success('user123', 5.00)
        
        mock_monitoring.payment_monitor.record_payment_attempt.assert_called_once_with(
            'user123', 5.00, True
        )
    
    @patch('monitoring.monitoring')
    def test_create_alert_function(self, mock_monitoring):
        """Test alert creation convenience function"""
        create_alert('warning', 'Test Alert', 'Test message', {'key': 'value'})
        
        mock_monitoring.create_alert.assert_called_once()
        
        # Verify alert severity was converted properly
        call_args = mock_monitoring.create_alert.call_args
        assert call_args[0][0] == AlertSeverity.WARNING

class TestPerformanceDecorator:
    """Test the performance monitoring decorator"""
    
    def test_monitor_performance_decorator(self):
        """Test performance monitoring decorator works"""
        
        @monitor_performance('test_function')
        def test_function():
            import time
            time.sleep(0.01)  # Small delay
            return 'success'
        
        with patch('monitoring.monitoring') as mock_monitoring:
            result = test_function()
            
            assert result == 'success'
            mock_monitoring.system_monitor.start_timer.assert_called_once_with('test_function')
            mock_monitoring.system_monitor.end_timer.assert_called_once()
    
    def test_monitor_performance_decorator_with_exception(self):
        """Test performance decorator handles exceptions"""
        
        @monitor_performance('failing_function')
        def failing_function():
            raise ValueError('Test error')
        
        with patch('monitoring.monitoring') as mock_monitoring:
            with pytest.raises(ValueError):
                failing_function()
            
            # Should still record the timer and error
            mock_monitoring.system_monitor.start_timer.assert_called_once()
            mock_monitoring.system_monitor.end_timer.assert_called_once()
            mock_monitoring.system_monitor.record_error.assert_called_once()

class TestIntegration:
    """Integration tests for monitoring system"""
    
    def test_monitoring_integration_with_flask(self, clean_monitoring):
        """Test monitoring works within Flask application context"""
        manager = MonitoringManager()
        
        # Should be able to create alerts and record metrics
        manager.create_alert(AlertSeverity.INFO, 'Test', 'Integration test')
        manager.system_monitor.record_metric('test_metric', 1.0)
        
        assert len(manager.alerts) == 1
        assert 'test_metric' in manager.system_monitor.metrics
    
    def test_monitoring_thread_safety(self, clean_monitoring):
        """Test monitoring is thread-safe"""
        import threading
        
        manager = MonitoringManager()
        results = []
        
        def create_alerts():
            for i in range(10):
                manager.create_alert(AlertSeverity.INFO, f'Alert {i}', f'Message {i}')
        
        # Create multiple threads
        threads = [threading.Thread(target=create_alerts) for _ in range(3)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have all alerts without race conditions
        assert len(manager.alerts) == 30

class TestAlertSeverity:
    """Test alert severity levels"""
    
    def test_alert_severity_values(self):
        """Test alert severity enum values"""
        assert AlertSeverity.INFO.value == 'info'
        assert AlertSeverity.WARNING.value == 'warning'
        assert AlertSeverity.ERROR.value == 'error'
        assert AlertSeverity.CRITICAL.value == 'critical'
    
    def test_alert_creation_with_all_severities(self):
        """Test creating alerts with all severity levels"""
        manager = MonitoringManager()
        
        severities = [AlertSeverity.INFO, AlertSeverity.WARNING, AlertSeverity.ERROR, AlertSeverity.CRITICAL]
        
        for severity in severities:
            manager.create_alert(severity, f'{severity.value} Alert', f'{severity.value} message')
        
        assert len(manager.alerts) == 4
        
        # Verify each severity was recorded
        recorded_severities = [alert.severity for alert in manager.alerts]
        for severity in severities:
            assert severity in recorded_severities
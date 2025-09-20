"""
Logging and monitoring utilities for MedSAGE application
"""
import logging
import os
import sys
from datetime import datetime
from functools import wraps
from flask import request, g, current_app
import time
import json

def setup_logging(app):
    """Setup comprehensive logging for the application."""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(app.config.get('LOG_FILE', 'logs/medsage.log'))
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure logging level
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper())
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    
    json_formatter = JsonFormatter()
    
    # File handler for general logs
    file_handler = logging.FileHandler(app.config.get('LOG_FILE', 'logs/medsage.log'))
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    
    # File handler for security events
    security_handler = logging.FileHandler('logs/security.log')
    security_handler.setLevel(logging.WARNING)
    security_handler.setFormatter(json_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(detailed_formatter)
    
    # Configure app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    
    # Create security logger
    security_logger = logging.getLogger('security')
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.WARNING)
    
    # Create audit logger
    audit_logger = logging.getLogger('audit')
    audit_handler = logging.FileHandler('logs/audit.log')
    audit_handler.setFormatter(json_formatter)
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'module': record.module,
            'message': record.getMessage(),
            'pathname': record.pathname,
            'lineno': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'ip_address'):
            log_entry['ip_address'] = record.ip_address
        
        return json.dumps(log_entry)

def log_request_info(f):
    """Decorator to log request information."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        
        # Generate request ID
        request_id = f"{datetime.utcnow().timestamp():.6f}"
        g.request_id = request_id
        
        # Log request start
        current_app.logger.info(
            f"Request started: {request.method} {request.path}",
            extra={
                'request_id': request_id,
                'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
                'user_agent': request.headers.get('User-Agent', ''),
                'method': request.method,
                'path': request.path
            }
        )
        
        try:
            result = f(*args, **kwargs)
            
            # Log successful request
            duration = time.time() - start_time
            current_app.logger.info(
                f"Request completed: {request.method} {request.path} - {duration:.3f}s",
                extra={
                    'request_id': request_id,
                    'duration_seconds': duration,
                    'status': 'success'
                }
            )
            
            return result
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            current_app.logger.error(
                f"Request failed: {request.method} {request.path} - {str(e)}",
                extra={
                    'request_id': request_id,
                    'duration_seconds': duration,
                    'status': 'error',
                    'error': str(e)
                }
            )
            raise
    
    return decorated_function

def log_security_event(event_type, details, severity='WARNING'):
    """Log security-related events."""
    security_logger = logging.getLogger('security')
    
    log_data = {
        'event_type': event_type,
        'details': details,
        'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr) if request else None,
        'user_agent': request.headers.get('User-Agent', '') if request else None,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if severity == 'ERROR':
        security_logger.error(json.dumps(log_data))
    elif severity == 'WARNING':
        security_logger.warning(json.dumps(log_data))
    else:
        security_logger.info(json.dumps(log_data))

def log_audit_event(action, resource, user_id=None, details=None):
    """Log audit events for compliance."""
    audit_logger = logging.getLogger('audit')
    
    audit_data = {
        'action': action,
        'resource': resource,
        'user_id': user_id,
        'details': details or {},
        'timestamp': datetime.utcnow().isoformat(),
        'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr) if request else None
    }
    
    audit_logger.info(json.dumps(audit_data))

class HealthChecker:
    """Health check utilities for monitoring."""
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
    
    def check_database(self):
        """Check database connectivity."""
        try:
            if self.db_manager:
                # Simple ping to check connection
                self.db_manager.client.admin.command('ping')
                return True, "Database connection healthy"
            return False, "Database manager not configured"
        except Exception as e:
            return False, f"Database connection failed: {str(e)}"
    
    def check_disk_space(self, threshold_percent=80):
        """Check available disk space."""
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            percent_used = (used / total) * 100
            
            if percent_used > threshold_percent:
                return False, f"Disk usage {percent_used:.1f}% exceeds threshold {threshold_percent}%"
            
            return True, f"Disk usage {percent_used:.1f}% is healthy"
        except Exception as e:
            return False, f"Disk space check failed: {str(e)}"
    
    def check_memory_usage(self, threshold_percent=80):
        """Check memory usage."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            
            if memory.percent > threshold_percent:
                return False, f"Memory usage {memory.percent:.1f}% exceeds threshold {threshold_percent}%"
            
            return True, f"Memory usage {memory.percent:.1f}% is healthy"
        except ImportError:
            return True, "Memory check skipped (psutil not available)"
        except Exception as e:
            return False, f"Memory check failed: {str(e)}"
    
    def get_health_status(self):
        """Get overall health status."""
        checks = {
            'database': self.check_database(),
            'disk_space': self.check_disk_space(),
            'memory': self.check_memory_usage()
        }
        
        overall_healthy = all(check[0] for check in checks.values())
        
        return {
            'healthy': overall_healthy,
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {
                name: {'status': 'healthy' if status else 'unhealthy', 'message': message}
                for name, (status, message) in checks.items()
            }
        }

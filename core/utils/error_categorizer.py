#!/usr/bin/env python3
"""
Error categorization utility for task error messages.
Categorizes errors into types like 'Auth', 'No file', 'Rate limit', etc.
"""

from typing import Optional, Dict, List
import re


class ErrorCategorizer:
    """Categorizes error messages into types."""
    
    # Error patterns mapped to categories
    ERROR_PATTERNS = {
        'Auth': [
            r'invalid_grant',
            r'Token.*expired',
            r'Token.*revoked',
            r'authentication.*error',
            r'auth.*failed',
            r'credentials.*invalid',
            r'oauth.*error',
            r'access.*denied',
            r'unauthorized',
            r'401',
            r'403'
        ],
        'No file': [
            r'file.*not.*found',
            r'file.*does.*not.*exist',
            r'no.*such.*file',
            r'cannot.*find.*file',
            r'path.*not.*found',
            r'video.*file.*not.*found',
            r'file.*missing'
        ],
        'Rate limit': [
            r'rate.*limit',
            r'quota.*exceeded',
            r'too.*many.*requests',
            r'429',
            r'503'
        ],
        'Upload': [
            r'upload.*failed',
            r'upload.*error',
            r'failed.*to.*upload',
            r'upload.*timeout',
            r'network.*error',
            r'connection.*error'
        ],
        'Channel': [
            r'channel.*not.*found',
            r'channel.*disabled',
            r'account.*not.*found',
            r'invalid.*channel'
        ],
        'Format': [
            r'invalid.*format',
            r'unsupported.*format',
            r'file.*format.*error',
            r'codec.*error'
        ],
        'Size': [
            r'file.*too.*large',
            r'size.*exceeded',
            r'max.*size',
            r'file.*size.*limit'
        ],
        'Unknown': []
    }
    
    @classmethod
    def categorize(cls, error_message: Optional[str]) -> str:
        """
        Categorize an error message into a type.
        
        Args:
            error_message: Error message string
            
        Returns:
            Error category string (e.g., 'Auth', 'No file', 'Unknown')
        """
        if not error_message:
            return 'Unknown'
        
        error_lower = error_message.lower()
        
        # Check each category's patterns
        for category, patterns in cls.ERROR_PATTERNS.items():
            if category == 'Unknown':
                continue
                
            for pattern in patterns:
                if re.search(pattern, error_lower, re.IGNORECASE):
                    return category
        
        return 'Unknown'
    
    @classmethod
    def get_error_types_for_tasks(cls, tasks: List[Dict]) -> Dict[int, List[str]]:
        """
        Get error types for a list of tasks.
        
        Args:
            tasks: List of task dictionaries with 'error_message' field
            
        Returns:
            Dictionary mapping account_id to list of error types
        """
        account_errors = {}
        
        for task in tasks:
            account_id = task.get('account_id')
            error_message = task.get('error_message')
            
            if error_message and account_id:
                error_type = cls.categorize(error_message)
                
                if account_id not in account_errors:
                    account_errors[account_id] = []
                
                account_errors[account_id].append(error_type)
        
        return account_errors
    
    @classmethod
    def format_error_types(cls, error_types: List[str]) -> str:
        """
        Format a list of error types for display.
        
        Args:
            error_types: List of error type strings
            
        Returns:
            Formatted string like "Auth, No file"
        """
        if not error_types:
            return ''
        
        # Count occurrences
        error_counts = {}
        for error_type in error_types:
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        # Format: show each type, with count if > 1
        formatted = []
        for error_type, count in sorted(error_counts.items()):
            if count > 1:
                formatted.append(f"{error_type} ({count}x)")
            else:
                formatted.append(error_type)
        
        return ', '.join(formatted)


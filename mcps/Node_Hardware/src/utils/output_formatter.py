"""
Beautiful output formatting utilities for Node Hardware MCP server.
Provides structured, readable, and visually appealing output formatting.
"""
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import psutil
import platform


class NodeHardwareFormatter:
    """
    A comprehensive formatter for creating beautiful, structured output
    that enhances readability and provides consistent formatting across
    all node hardware MCP operations.
    """
    
    @staticmethod
    def format_success_response(
        operation: str,
        data: Any,
        summary: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        insights: Optional[List[str]] = None,
        hostname: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format a successful operation response with beautiful structure.
        
        Args:
            operation: Name of the operation performed
            data: Main data result
            summary: Summary statistics or information
            metadata: Additional metadata about the operation
            insights: Key insights or recommendations
            hostname: Target hostname for remote operations
            
        Returns:
            Beautifully formatted response dictionary
        """
        response: Dict[str, Any] = {
            "🖥️ Operation": operation.replace("_", " ").title(),
            "✅ Status": "Success",
            "⏰ Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "🔧 Hardware Data": NodeHardwareFormatter._format_hardware_data(data)
        }
        
        if hostname:
            response["🌐 Target Host"] = hostname
            
        if summary:
            response["📊 Summary"] = NodeHardwareFormatter._format_summary(summary)
            
        if metadata:
            response["🔍 Metadata"] = NodeHardwareFormatter._format_metadata(metadata)
            
        if insights:
            response["💡 Insights"] = NodeHardwareFormatter._format_insights(insights)
            
        return response
    
    @staticmethod
    def format_error_response(
        operation: str,
        error_message: str,
        error_type: str,
        suggestions: Optional[List[str]] = None,
        hostname: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format an error response with helpful information.
        
        Args:
            operation: Name of the operation that failed
            error_message: Detailed error message
            error_type: Type of error that occurred
            suggestions: Suggested solutions or next steps
            hostname: Target hostname for remote operations
            
        Returns:
            Beautifully formatted error response
        """
        response: Dict[str, Any] = {
            "🖥️ Operation": operation.replace("_", " ").title(),
            "❌ Status": "Error",
            "⏰ Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "🚨 Error Type": error_type,
            "📝 Error Message": error_message
        }
        
        if hostname:
            response["🌐 Target Host"] = hostname
            
        if suggestions:
            response["💭 Suggestions"] = NodeHardwareFormatter._format_suggestions(suggestions)
            
        return response
    
    @staticmethod
    def _format_hardware_data(data: Any) -> Any:
        """Format hardware data with appropriate structure."""
        if isinstance(data, dict):
            return NodeHardwareFormatter._format_dict(data)
        elif isinstance(data, list):
            return NodeHardwareFormatter._format_list(data)
        else:
            return data
    
    @staticmethod
    def _format_dict(data: Dict) -> Dict:
        """Format dictionary with nested structure handling."""
        formatted = {}
        for key, value in data.items():
            # Add appropriate emoji prefixes for common hardware items
            if "cpu" in key.lower():
                formatted_key = f"⚡ {key.replace('_', ' ').title()}"
            elif "memory" in key.lower() or "ram" in key.lower():
                formatted_key = f"💾 {key.replace('_', ' ').title()}"
            elif "disk" in key.lower() or "storage" in key.lower():
                formatted_key = f"💿 {key.replace('_', ' ').title()}"
            elif "network" in key.lower():
                formatted_key = f"🌐 {key.replace('_', ' ').title()}"
            elif "gpu" in key.lower():
                formatted_key = f"🎮 {key.replace('_', ' ').title()}"
            elif "temperature" in key.lower() or "sensor" in key.lower():
                formatted_key = f"🌡️ {key.replace('_', ' ').title()}"
            elif "process" in key.lower():
                formatted_key = f"🔄 {key.replace('_', ' ').title()}"
            elif "system" in key.lower() or "os" in key.lower():
                formatted_key = f"🖥️ {key.replace('_', ' ').title()}"
            elif "uptime" in key.lower():
                formatted_key = f"⏱️ {key.replace('_', ' ').title()}"
            elif "user" in key.lower():
                formatted_key = f"👤 {key.replace('_', ' ').title()}"
            elif "boot" in key.lower():
                formatted_key = f"🚀 {key.replace('_', ' ').title()}"
            elif "error" in key.lower():
                formatted_key = f"🚨 {key.replace('_', ' ').title()}"
            elif "usage" in key.lower():
                formatted_key = f"📊 {key.replace('_', ' ').title()}"
            elif "frequency" in key.lower():
                formatted_key = f"⚡ {key.replace('_', ' ').title()}"
            elif "speed" in key.lower():
                formatted_key = f"🏃 {key.replace('_', ' ').title()}"
            elif "capacity" in key.lower() or "size" in key.lower():
                formatted_key = f"📏 {key.replace('_', ' ').title()}"
            else:
                formatted_key = f"🔧 {key.replace('_', ' ').title()}"
            
            if isinstance(value, (dict, list)):
                formatted[formatted_key] = NodeHardwareFormatter._format_hardware_data(value)
            else:
                formatted[formatted_key] = value
        return formatted
    
    @staticmethod
    def _format_list(data: List) -> List:
        """Format list with appropriate item formatting."""
        return [NodeHardwareFormatter._format_hardware_data(item) for item in data]
    
    @staticmethod
    def _format_summary(summary: Dict) -> Dict:
        """Format summary information with visual enhancements."""
        formatted_summary = {}
        
        for key, value in summary.items():
            # Add appropriate emoji prefixes for common summary items
            if "count" in key.lower():
                formatted_key = f"📊 {key.replace('_', ' ').title()}"
            elif "total" in key.lower():
                formatted_key = f"📈 {key.replace('_', ' ').title()}"
            elif "time" in key.lower():
                formatted_key = f"⏱️ {key.replace('_', ' ').title()}"
            elif "size" in key.lower() or "memory" in key.lower():
                formatted_key = f"💾 {key.replace('_', ' ').title()}"
            elif "error" in key.lower():
                formatted_key = f"🚨 {key.replace('_', ' ').title()}"
            elif "success" in key.lower():
                formatted_key = f"✅ {key.replace('_', ' ').title()}"
            elif "host" in key.lower():
                formatted_key = f"🌐 {key.replace('_', ' ').title()}"
            elif "nodes" in key.lower():
                formatted_key = f"🖥️ {key.replace('_', ' ').title()}"
            else:
                formatted_key = f"📋 {key.replace('_', ' ').title()}"
            
            formatted_summary[formatted_key] = value
        
        return formatted_summary
    
    @staticmethod
    def _format_metadata(metadata: Dict) -> Dict:
        """Format metadata with visual enhancements."""
        formatted_metadata = {}
        
        for key, value in metadata.items():
            # Add appropriate emoji prefixes for metadata items
            if "hostname" in key.lower():
                formatted_key = f"🌐 {key.replace('_', ' ').title()}"
            elif "user" in key.lower():
                formatted_key = f"👤 {key.replace('_', ' ').title()}"
            elif "method" in key.lower():
                formatted_key = f"🔧 {key.replace('_', ' ').title()}"
            elif "protocol" in key.lower():
                formatted_key = f"🔌 {key.replace('_', ' ').title()}"
            elif "port" in key.lower():
                formatted_key = f"🚪 {key.replace('_', ' ').title()}"
            elif "timeout" in key.lower():
                formatted_key = f"⏳ {key.replace('_', ' ').title()}"
            elif "version" in key.lower():
                formatted_key = f"📋 {key.replace('_', ' ').title()}"
            else:
                formatted_key = f"ℹ️ {key.replace('_', ' ').title()}"
            
            formatted_metadata[formatted_key] = value
        
        return formatted_metadata
    
    @staticmethod
    def _format_insights(insights: List[str]) -> List[str]:
        """Format insights with visual enhancements."""
        formatted_insights = []
        
        for insight in insights:
            if "error" in insight.lower() or "fail" in insight.lower():
                formatted_insights.append(f"🚨 {insight}")
            elif "warning" in insight.lower() or "high" in insight.lower():
                formatted_insights.append(f"⚠️ {insight}")
            elif "good" in insight.lower() or "success" in insight.lower():
                formatted_insights.append(f"✅ {insight}")
            elif "recommend" in insight.lower() or "suggest" in insight.lower():
                formatted_insights.append(f"💡 {insight}")
            else:
                formatted_insights.append(f"ℹ️ {insight}")
        
        return formatted_insights
    
    @staticmethod
    def _format_suggestions(suggestions: List[str]) -> List[str]:
        """Format suggestions with visual enhancements."""
        formatted_suggestions = []
        
        for suggestion in suggestions:
            formatted_suggestions.append(f"💭 {suggestion}")
        
        return formatted_suggestions
    
    @staticmethod
    def create_filtered_response(
        operation: str,
        data: Any,
        filters: Optional[Dict] = None,
        total_items: Optional[int] = None,
        filtered_items: Optional[int] = None
    ) -> Dict:
        """
        Create a filtered response with filter information.
        
        Args:
            operation: Name of the operation
            data: Filtered data
            filters: Applied filters
            total_items: Total number of items before filtering
            filtered_items: Number of items after filtering
            
        Returns:
            Beautifully formatted filtered response
        """
        response = NodeHardwareFormatter.format_success_response(
            operation=operation,
            data=data
        )
        
        if filters:
            response["🔍 Applied Filters"] = NodeHardwareFormatter._format_dict(filters)
        
        if total_items is not None and filtered_items is not None:
            response["📊 Filter Results"] = {
                "🔢 Total Items": total_items,
                "✅ Filtered Items": filtered_items,
                "📉 Filtered Out": total_items - filtered_items,
                "📊 Filter Ratio": f"{(filtered_items / total_items * 100):.1f}%" if total_items > 0 else "0%"
            }
        
        return response


def create_beautiful_response(
    operation: str,
    success: bool,
    data: Any = None,
    summary: Optional[Dict] = None,
    metadata: Optional[Dict] = None,
    insights: Optional[List[str]] = None,
    hostname: Optional[str] = None,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
    suggestions: Optional[List[str]] = None,
    **kwargs
) -> Dict:
    """
    Create a beautiful response with MCP-compliant format.
    
    Args:
        operation: Name of the operation
        success: Whether the operation was successful
        data: Main data result
        summary: Summary information
        metadata: Additional metadata
        insights: Key insights
        hostname: Target hostname
        error_message: Error message if failed
        error_type: Error type if failed
        suggestions: Suggestions if failed
        **kwargs: Additional arguments
        
    Returns:
        MCP-compliant response with beautiful formatting
    """
    if success:
        formatted_response = NodeHardwareFormatter.format_success_response(
            operation=operation,
            data=data,
            summary=summary,
            metadata=metadata,
            insights=insights,
            hostname=hostname
        )
    else:
        formatted_response = NodeHardwareFormatter.format_error_response(
            operation=operation,
            error_message=error_message or "Unknown error",
            error_type=error_type or "UnknownError",
            suggestions=suggestions,
            hostname=hostname
        )
    
    return {
        "content": [{"text": json.dumps(formatted_response, indent=2)}],
        "_meta": {
            "tool": operation,
            "success": success,
            "hostname": hostname
        },
        "isError": not success
    } 
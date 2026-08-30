"""
GCP Cloud Logging & Monitoring Client - Execute real queries against GCP APIs

Uses google-cloud-logging and google-cloud-monitoring Python clients to query:
- Cloud Logging for application logs
- Cloud Monitoring for CPU, Memory, Network metrics
- Load Balancer logs from Cloud Logging

MOCK MODE: Set GCP_MOCK_MODE=true to return instant mock data (for testing/demos)
"""

import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.cloud import logging as cloud_logging
from google.cloud import monitoring_v3

from agents.gcp_rca_agent.config import GCPConfig

logger = logging.getLogger(__name__)

# MOCK MODE - returns instant data without API calls
GCP_MOCK_MODE = os.getenv("GCP_MOCK_MODE", "false").lower() == "true"


class GCPLoggingClient:
    """Cloud Logging client for querying application and infrastructure logs."""
    
    _client = None
    _container_name_cache = {}  # Cache: {(namespace, pod_prefix): container_name}
    
    @classmethod
    def get_client(cls):
        """Get or create Cloud Logging client."""
        if cls._client is None:
            try:
                credentials = GCPConfig.get_credentials()
                project_id = GCPConfig.get_project_id()
                cls._client = cloud_logging.Client(
                    project=project_id,
                    credentials=credentials
                )
            except Exception as e:
                logger.error(f"Failed to initialize Cloud Logging client: {e}")
                raise
        return cls._client
    
    @classmethod
    def get_log_entries(
        cls,
        pod_name: str,
        namespace: str,
        lines: int = 100,
        error_only: bool = False
    ) -> Dict[str, Any]:
        """
        Query Cloud Logging for pod logs.
        
        Args:
            pod_name: Pod name/selector
            namespace: Kubernetes namespace
            lines: Number of log entries to retrieve
            error_only: Return only ERROR and FATAL logs
        
        Returns:
            Dictionary with log entries
        """
        import time
        start = time.time()
        
        # MOCK MODE - return instant data
        if GCP_MOCK_MODE:
            return cls._mock_get_log_entries(pod_name, namespace, lines)
        
        try:
            client = cls.get_client()
            project_id = GCPConfig.get_project_id()
            logger.info(f"[TIMING] get_log_entries START for {pod_name} in {namespace}")
            
            # Build Cloud Logging Insights query
            filter_str = f'''
                resource.type="k8s_container"
                resource.labels.namespace_name="{namespace}"
                resource.labels.pod_name=~"{pod_name}.*"
            '''
            
            if error_only:
                filter_str += ' severity >= ERROR'
            
            # Query logs (most recent first, limit to lines)
            entries = list(client.list_entries(
                filter_=filter_str,
                page_size=lines,
                order_by=cloud_logging.DESCENDING
            ))
            
            formatted_logs = []
            for entry in entries:
                log_entry = {
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else "",
                    "severity": entry.severity or "DEFAULT",
                    "message": entry.payload if isinstance(entry.payload, str) else str(entry.payload),
                    "pod_name": entry.labels.get("pod_name", pod_name) if hasattr(entry, 'labels') else pod_name
                }
                formatted_logs.append(log_entry)
            
            # Extract and cache container name from first log entry for faster metric queries
            if formatted_logs and not cls._container_name_cache.get((namespace, pod_name)):
                try:
                    # Try to get container name from resource labels
                    for entry in entries:
                        if hasattr(entry, 'resource') and hasattr(entry.resource, 'labels'):
                            container_name = entry.resource.labels.get('container_name')
                            if container_name:
                                cls._container_name_cache[(namespace, pod_name)] = container_name
                                logger.debug(f"Cached container name '{container_name}' for {namespace}/{pod_name}")
                                break
                except Exception as e:
                    logger.debug(f"Could not extract container name: {e}")
            
            elapsed = time.time() - start
            logger.info(f"[TIMING] get_log_entries DONE in {elapsed:.2f}s for {pod_name}")
            
            return {
                "status": "success",
                "pod_name": pod_name,
                "namespace": namespace,
                "log_count": len(formatted_logs),
                "logs": formatted_logs,
                "container_name": cls._container_name_cache.get((namespace, pod_name))
            }
        
        except Exception as e:
            logger.error(f"Error querying logs for {pod_name}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "pod_name": pod_name,
                "namespace": namespace
            }
    
    @classmethod
    def execute_logging_query(
        cls,
        query: str,
        time_range: str = "1h"
    ) -> Dict[str, Any]:
        """
        Execute Cloud Logging Insights query.
        
        Args:
            query: Cloud Logging query string (LQL)
            time_range: Time range for query (e.g., "1h", "30m")
        
        Returns:
            Dictionary with query results
        """
        try:
            client = cls.get_client()
            
            # Calculate time range
            end_time = datetime.utcnow()
            if time_range.endswith('h'):
                hours = int(time_range[:-1])
                start_time = end_time - timedelta(hours=hours)
            elif time_range.endswith('m'):
                minutes = int(time_range[:-1])
                start_time = end_time - timedelta(minutes=minutes)
            else:
                start_time = end_time - timedelta(hours=1)
            
            # Execute query with time range
            entries = list(client.list_entries(
                filter_=query,
                page_size=100
            ))
            
            return {
                "status": "success",
                "query": query,
                "time_range": time_range,
                "result_count": len(entries),
                "results": [
                    {
                        "timestamp": e.timestamp.isoformat() if e.timestamp else "",
                        "severity": e.severity or "DEFAULT",
                        "message": e.payload if isinstance(e.payload, str) else str(e.payload)
                    }
                    for e in entries
                ]
            }
        
        except Exception as e:
            logger.error(f"Error executing logging query: {e}")
            return {
                "status": "error",
                "error": str(e),
                "query": query
            }
    
    @classmethod
    def _mock_get_log_entries(cls, pod_name: str, namespace: str, lines: int) -> Dict[str, Any]:
        """Return mock log data instantly (no API call)."""
        if "backend" in pod_name.lower():
            logs = [
                {"timestamp": "2024-11-26T10:15:23Z", "severity": "INFO", "message": f"[INFO] Starting {pod_name}"},
                {"timestamp": "2024-11-26T10:15:26Z", "severity": "ERROR", "message": "[ERROR] Failed to load config"},
                {"timestamp": "2024-11-26T10:15:27Z", "severity": "ERROR", "message": "[ERROR] NullPointerException"},
                {"timestamp": "2024-11-26T10:15:30Z", "severity": "CRITICAL", "message": "[FATAL] Exiting"},
            ]
        else:
            logs = [
                {"timestamp": "2024-11-26T10:15:23Z", "severity": "INFO", "message": f"[INFO] Starting {pod_name}"},
                {"timestamp": "2024-11-26T10:15:24Z", "severity": "INFO", "message": "[INFO] Ready"},
                {"timestamp": "2024-11-26T10:16:00Z", "severity": "INFO", "message": "[INFO] GET /api/health 200"},
            ]
        
        return {
            "status": "success",
            "pod_name": pod_name,
            "namespace": namespace,
            "log_count": len(logs),
            "logs": logs[:lines],
            "container_name": pod_name  # Mock container name
        }


class GCPMonitoringClient:
    """Cloud Monitoring client for querying metrics."""
    
    _client = None
    
    @classmethod
    def get_client(cls):
        """Get or create Cloud Monitoring client."""
        if cls._client is None:
            try:
                credentials = GCPConfig.get_credentials()
                project_id = GCPConfig.get_project_id()
                cls._client = monitoring_v3.MetricServiceClient(
                    credentials=credentials
                )
                cls._project_name = f"projects/{project_id}"
            except Exception as e:
                logger.error(f"Failed to initialize Cloud Monitoring client: {e}")
                raise
        return cls._client
    
    @classmethod
    def get_monitoring_metrics(
        cls,
        pod_name: str,
        namespace: str,
        time_range_minutes: int = 5,  # Reduced from 15 to 5 for faster queries
        container_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query Cloud Monitoring for pod CPU and Memory metrics.
        
        Args:
            pod_name: Pod name or deployment name
            namespace: Kubernetes namespace
            time_range_minutes: Minutes of history to retrieve (default: 5)
            container_name: Optional container name for direct lookup (faster)
        
        Returns:
            Dictionary with CPU and Memory utilization
        """
        import time
        start = time.time()
        logger.info(f"[TIMING] get_monitoring_metrics START for {pod_name} in {namespace}")
        
        # MOCK MODE - return instant data
        if GCP_MOCK_MODE:
            return cls._mock_get_metrics(pod_name, namespace)
        
        try:
            client = cls.get_client()
            project_id = GCPConfig.get_project_id()
            project_name = f"projects/{project_id}"
            
            # Try to get container name from cache if not provided
            if not container_name:
                container_name = GCPLoggingClient._container_name_cache.get((namespace, pod_name))
            
            now = datetime.utcnow()
            minutes_ago = now - timedelta(minutes=time_range_minutes)
            
            # Parallel execution of CPU and Memory queries for 2x speed improvement
            cpu_response = {}
            memory_response = {}
            
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both queries in parallel
                cpu_future = executor.submit(
                    cls._query_metric_with_fallback,
                    metric_types=[
                        "kubernetes.io/container/cpu/core_usage_time",
                        "kubernetes.io/container/cpu/limit_utilization",
                        "kubernetes.io/container/cpu/request_utilization",
                    ],
                    pod_name=pod_name,
                    namespace=namespace,
                    project_name=project_name,
                    container_name=container_name
                )
                
                memory_future = executor.submit(
                    cls._query_metric_with_fallback,
                    metric_types=[
                        "kubernetes.io/container/memory/used_bytes",
                        "kubernetes.io/container/memory/limit_utilization",
                        "kubernetes.io/container/memory/request_utilization",
                    ],
                    pod_name=pod_name,
                    namespace=namespace,
                    project_name=project_name,
                    container_name=container_name
                )
                
                # Wait for both to complete
                cpu_response = cpu_future.result(timeout=30)
                memory_response = memory_future.result(timeout=30)
            
            # Calculate utilization percentages
            cpu_percent = cls._calculate_cpu_percent(cpu_response)
            memory_percent = cls._calculate_memory_percent(memory_response)
            
            elapsed = time.time() - start
            logger.info(f"[TIMING] get_monitoring_metrics DONE in {elapsed:.2f}s for {pod_name}")
            
            return {
                "status": "success",
                "pod_name": pod_name,
                "namespace": namespace,
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory_percent,
                "cpu_datapoints": cpu_response.get("datapoints", []),
                "memory_datapoints": memory_response.get("datapoints", [])
            }
        
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"[TIMING] get_monitoring_metrics FAILED in {elapsed:.2f}s for {pod_name}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "pod_name": pod_name,
                "namespace": namespace
            }
    
    @classmethod
    def _query_metric(
        cls,
        metric_type: str,
        pod_name: str,
        namespace: str,
        project_name: str,
        container_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a single metric query with optimized filtering."""
        try:
            client = cls.get_client()
            
            # Build resource filter for container metrics
            # OPTIMIZATION: If container_name is known, use direct match (much faster)
            # Otherwise, query by namespace only and filter client-side
            resource_filter = f'resource.labels.namespace_name="{namespace}"'
            
            if container_name:
                # Direct container name match - fastest approach
                resource_filter += f' AND resource.labels.container_name="{container_name}"'
                logger.debug(f"Using direct container_name filter: {container_name}")
            
            # Query time series with optimized time range
            interval = monitoring_v3.TimeInterval({
                "end_time": {"seconds": int(datetime.utcnow().timestamp())},
                "start_time": {"seconds": int((datetime.utcnow() - timedelta(minutes=5)).timestamp())}
            })
            
            results = client.list_time_series(
                request={
                    "name": project_name,
                    "filter": f'metric.type="{metric_type}" AND {resource_filter}',
                    "interval": interval
                }
            )
            
            datapoints = []
            for result in results:
                # If container_name filter was used, no client-side filtering needed
                if container_name:
                    for point in result.points:
                        datapoints.append({
                            "timestamp": point.interval.end_time.isoformat(),
                            "value": float(point.value.double_value) if point.value.double_value else 0,
                            "container": container_name
                        })
                else:
                    # Client-side filtering only when container_name not available
                    result_container_name = result.resource.labels.get("container_name", "")
                    result_pod_name = result.resource.labels.get("pod_name", "")
                    
                    # Match if container or pod name starts with deployment name
                    if (not pod_name or 
                        result_container_name.startswith(pod_name) or 
                        result_pod_name.startswith(pod_name)):
                        
                        for point in result.points:
                            datapoints.append({
                                "timestamp": point.interval.end_time.isoformat(),
                                "value": float(point.value.double_value) if point.value.double_value else 0,
                                "container": result_container_name,
                                "pod": result_pod_name
                            })
            
            return {
                "status": "success",
                "metric_type": metric_type,
                "datapoints": datapoints
            }
        
        except Exception as e:
            logger.error(f"Error querying metric {metric_type}: {e}")
            return {"status": "error", "error": str(e), "datapoints": []}
    
    @classmethod
    def _query_metric_with_fallback(
        cls,
        metric_types: List[str],
        pod_name: str,
        namespace: str,
        project_name: str,
        container_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query single metric type only (no fallback attempts).
        
        Optimization: Only query the first metric type to avoid multiple API calls.
        If metrics not available, return gracefully without retrying.
        """
        if not metric_types:
            return {
                "status": "success",
                "metric_type": "none",
                "datapoints": [],
                "message": "No metric types specified"
            }
        
        metric_type = metric_types[0]  # Use only first metric type
        
        try:
            result = cls._query_metric(
                metric_type=metric_type,
                pod_name=pod_name,
                namespace=namespace,
                project_name=project_name,
                container_name=container_name
            )
            
            # Return result as-is (even if empty)
            if result.get("status") == "success":
                logger.debug(f"Queried metric {metric_type} for {pod_name}")
                return result
            else:
                return {
                    "status": "success",
                    "metric_type": metric_type,
                    "datapoints": [],
                    "message": "Metrics not available for this pod"
                }
                    
        except Exception as e:
            logger.warning(f"Metric query failed for {metric_type}: {e}")
            # Return empty result without retrying other metric types
            return {
                "status": "success",
                "metric_type": metric_type,
                "datapoints": [],
                "message": "Metrics not available for this pod"
            }
    
    @classmethod
    def _calculate_cpu_percent(cls, response: Dict[str, Any]) -> float:
        """Calculate average CPU usage percentage."""
        try:
            datapoints = response.get("datapoints", [])
            if not datapoints:
                return 0.0
            
            # Assume values are in seconds, convert to percentage (simplified)
            values = [dp.get("value", 0) for dp in datapoints]
            return min(100.0, (sum(values) / len(values)) * 100) if values else 0.0
        except:
            return 0.0
    
    @classmethod
    def _calculate_memory_percent(cls, response: Dict[str, Any]) -> float:
        """Calculate average Memory usage percentage."""
        try:
            datapoints = response.get("datapoints", [])
            if not datapoints:
                return 0.0
            
            # Assume limit is 1GB, calculate percentage (simplified)
            values = [dp.get("value", 0) for dp in datapoints]
            if not values:
                return 0.0
            
            avg_bytes = sum(values) / len(values)
            memory_limit_bytes = 1024 * 1024 * 1024  # 1GB default
            return min(100.0, (avg_bytes / memory_limit_bytes) * 100)
        except:
            return 0.0
    
    @classmethod
    def _mock_get_metrics(cls, pod_name: str, namespace: str) -> Dict[str, Any]:
        """Return mock metrics instantly (no API call)."""
        if "backend" in pod_name.lower():
            return {
                "status": "success",
                "pod_name": pod_name,
                "namespace": namespace,
                "cpu_usage_percent": 88.5,
                "memory_usage_percent": 95.2,
                "cpu_datapoints": [],
                "memory_datapoints": []
            }
        else:
            return {
                "status": "success",
                "pod_name": pod_name,
                "namespace": namespace,
                "cpu_usage_percent": 25.3,
                "memory_usage_percent": 42.1,
                "cpu_datapoints": [],
                "memory_datapoints": []
            }


class GCPLoadBalancerClient:
    """Cloud Logging client for querying Load Balancer logs."""
    
    _logging_client = None
    
    @classmethod
    def get_logging_client(cls):
        """Get Cloud Logging client."""
        if cls._logging_client is None:
            credentials = GCPConfig.get_credentials()
            project_id = GCPConfig.get_project_id()
            cls._logging_client = cloud_logging.Client(
                project=project_id,
                credentials=credentials
            )
        return cls._logging_client
    
    @classmethod
    def get_load_balancer_logs(
        cls,
        lines: int = 50,
        status_code_filter: str = "",
        min_response_time_ms: int = 0
    ) -> Dict[str, Any]:
        """
        Query Cloud Logging for Cloud Load Balancer logs.
        
        Args:
            lines: Number of log entries to retrieve
            status_code_filter: Comma-separated status codes (e.g., "500,502,503")
            min_response_time_ms: Minimum response time in milliseconds
        
        Returns:
            Dictionary with HTTP requests and response codes
        """
        try:
            client = cls.get_logging_client()
            
            # Build filter for HTTP Load Balancer logs
            filter_str = 'resource.type="http_load_balancer"'
            
            if status_code_filter:
                status_codes = status_code_filter.split(",")
                status_filter = " OR ".join([f'httpRequest.status={code.strip()}' for code in status_codes])
                filter_str += f' AND ({status_filter})'
            
            if min_response_time_ms > 0:
                filter_str += f' AND httpRequest.latency >= {min_response_time_ms}ms'
            
            # Query logs
            entries = list(client.list_entries(
                filter_=filter_str,
                page_size=lines,
                order_by=cloud_logging.DESCENDING
            ))
            
            formatted_logs = []
            for entry in entries:
                http_req = getattr(entry, 'http_request', None)
                if http_req:
                    log_entry = {
                        "timestamp": entry.timestamp.isoformat() if entry.timestamp else "",
                        "request_method": http_req.request_method or "UNKNOWN",
                        "request_url": http_req.request_url or "",
                        "status": http_req.status or 0,
                        "latency_ms": cls._parse_latency(http_req.latency),
                        "user_agent": http_req.user_agent or "",
                        "response_size_bytes": http_req.response_size_bytes or 0
                    }
                    formatted_logs.append(log_entry)
            
            return {
                "status": "success",
                "log_count": len(formatted_logs),
                "logs": formatted_logs
            }
        
        except Exception as e:
            logger.error(f"Error querying load balancer logs: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    @classmethod
    def _parse_latency(cls, latency_str: str) -> int:
        """Parse latency string to milliseconds."""
        try:
            if not latency_str:
                return 0
            # Handle format like "1.234s"
            if latency_str.endswith('s'):
                return int(float(latency_str[:-1]) * 1000)
            elif latency_str.endswith('ms'):
                return int(latency_str[:-2])
            else:
                return int(float(latency_str) * 1000)
        except:
            return 0

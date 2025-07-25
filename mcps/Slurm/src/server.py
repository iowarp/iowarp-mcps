"""
Slurm MCP Server - Comprehensive HPC Job Management and Cluster Monitoring

This server provides comprehensive HPC job management and cluster monitoring capabilities through
the Model Context Protocol, enabling users to submit jobs, monitor cluster resources, and manage
workloads across Slurm-managed HPC systems with intelligent job scheduling and resource optimization.

Following MCP best practices, this server is designed with a workflow-first approach
providing intelligent, contextual assistance for HPC job management, cluster monitoring,
and resource optimization workflows.
"""

import os
import sys
import logging
from typing import Optional

# Try to import required dependencies with fallbacks
try:
    from fastmcp import FastMCP
except ImportError:
    print("FastMCP not available. Please install with: uv add fastmcp", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print(
        "Warning: python-dotenv not available. Environment variables may not be loaded.",
        file=sys.stderr,
    )

# Add current directory to path for relative imports
sys.path.insert(0, os.path.dirname(__file__))

# Import implementation modules directly
from implementation.job_submission import submit_slurm_job
from implementation.job_status import get_job_status
from implementation.job_cancellation import cancel_slurm_job
from implementation.job_listing import list_slurm_jobs
from implementation.cluster_info import get_slurm_info
from implementation.job_details import get_job_details
from implementation.job_output import get_job_output
from implementation.queue_info import get_queue_info
from implementation.array_jobs import submit_array_job
from implementation.node_info import get_node_info
from implementation.node_allocation import (
    allocate_nodes,
    deallocate_nodes,
    get_allocation_status,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server instance
mcp: FastMCP = FastMCP("Slurm-MCP-JobManagement")


# Custom exception for Slurm MCP errors
class SlurmMCPError(Exception):
    """Custom exception for Slurm MCP-related errors"""

    pass


# ═══════════════════════════════════════════════════════════════════════════════
# SLURM JOB MANAGEMENT TOOLS
# ═══════════════════════════════════════════════════════════════════════════════


@mcp.tool(
    name="submit_slurm_job",
    description="""Submit Slurm jobs with comprehensive resource specification and intelligent job optimization.

This powerful tool provides complete job submission capabilities by accepting script files and resource requirements,
then submitting them to the Slurm scheduler with advanced parameter validation, intelligent optimization, and 
comprehensive job lifecycle management.

**Intelligent Job Submission Strategy**:
1. **Resource Validation**: Comprehensive validation of CPU, memory, and time requirements with intelligent defaults and optimization
2. **Script Analysis**: Automatic analysis of script requirements and compatibility with cluster capabilities
3. **Queue Selection**: Smart partition and queue selection based on resource requirements, availability, and historical performance
4. **Intelligent Scheduling**: AI-powered scheduling recommendations based on cluster state, job characteristics, and performance patterns
5. **Performance Optimization**: Resource allocation optimization with efficiency analysis and cost-effectiveness recommendations

**Advanced Job Submission Features**:
- **Resource Requirements**: CPU cores, memory allocation, time limits with intelligent scaling and optimization
- **Queue Management**: Automatic partition selection with load balancing and performance optimization
- **Job Naming**: Intelligent job naming with metadata tracking and organization
- **Script Validation**: Comprehensive script analysis with compatibility checking and optimization suggestions
- **Resource Efficiency**: Automatic resource optimization with usage prediction and cost analysis
- **Job Prioritization**: Smart priority assignment based on resource requirements and cluster policies

**Optimization Intelligence**:
- **Resource Sizing**: Intelligent resource recommendation based on script analysis and historical data
- **Queue Selection**: Optimal partition selection based on resource availability and job characteristics
- **Time Estimation**: Intelligent time limit suggestions based on workload analysis and cluster performance
- **Cost Optimization**: Resource allocation optimization for cost-effectiveness and efficiency
- **Performance Prediction**: Job performance estimation with bottleneck identification and optimization

**Prerequisites**: Valid Slurm cluster access with job submission capabilities and script file availability
**Tools to use before this**: get_slurm_info() to verify cluster capabilities, get_queue_info() for availability analysis
**Tools to use after this**: check_job_status() for monitoring, get_job_details() for analysis, get_job_output() for results

Use this tool when:
- Submitting computational jobs to HPC clusters with optimized resource allocation ("Submit my parallel simulation with intelligent resource optimization")
- Deploying batch workloads with specific resource requirements and intelligent scheduling optimization
- Running scientific applications with AI-powered resource allocation and performance monitoring
- Executing high-throughput computing workflows with intelligent job scheduling and queue management
- Optimizing job submission for cost-effectiveness and performance efficiency with predictive analysis""",
)
async def submit_slurm_job_tool(
    script_path: str,
    cores: int = 1,
    memory: str = "1GB",
    time_limit: str = "01:00:00",
    job_name: Optional[str] = None,
    partition: Optional[str] = None,
) -> dict:
    """
    Submit a job script to Slurm scheduler with advanced resource specification and intelligent optimization.

    Args:
        script_path: Path to the job script file (required)
        cores: Number of CPU cores to request with intelligent resource allocation (default: 1, must be > 0)
        memory: Memory requirement with automatic unit conversion (e.g., "4G", "2048M", default: "1GB")
        time_limit: Time limit in HH:MM:SS format with intelligent duration estimation (default: "01:00:00")
        job_name: Custom job name for easy identification (default: derived from script filename)
        partition: Slurm partition selection with automatic queue optimization (default: system default)

    Returns:
        Dictionary containing comprehensive job submission results with scheduling insights
    """
    try:
        logger.info(
            f"Submitting comprehensive Slurm job: {script_path} with {cores} cores and advanced resource optimization"
        )

        return submit_slurm_job(
            script_path, cores, memory, time_limit, job_name, partition
        )
    except Exception as e:
        logger.error(f"Job submission error: {e}")
        return {
            "content": [
                {
                    "text": f'{{"success": false, "error": "{str(e)}", "error_type": "JobSubmissionError", "troubleshooting": "Check script path, resource requirements, and cluster connectivity"}}'
                }
            ],
            "_meta": {"tool": "submit_slurm_job", "error": "JobSubmissionError"},
            "isError": True,
        }


@mcp.tool(
    name="check_job_status",
    description="""Check comprehensive Slurm job status with advanced monitoring, performance insights, and intelligent analysis.

This powerful tool provides complete job status analysis by querying the Slurm scheduler and delivering detailed 
status information with intelligent analysis, performance metrics, optimization recommendations, and predictive insights
for comprehensive job lifecycle management.

**Intelligent Job Status Analysis**:
1. **Real-Time Monitoring**: Comprehensive job state tracking with performance analysis and trend monitoring
2. **Performance Analytics**: Resource utilization analysis with efficiency metrics and optimization insights
3. **Predictive Analysis**: Job completion estimation with performance trend analysis and bottleneck identification
4. **Health Assessment**: Job health monitoring with issue detection and optimization recommendations
5. **Resource Optimization**: Usage pattern analysis with efficiency recommendations and cost optimization

**Advanced Status Information**:
- **Job State Tracking**: Current status, queue position, execution progress with intelligent state analysis
- **Resource Utilization**: CPU, memory, I/O usage with efficiency analysis and optimization recommendations
- **Performance Metrics**: Runtime analysis, throughput measurement, and performance trend identification
- **Queue Analytics**: Position analysis, estimated wait time, and scheduling optimization insights
- **Error Detection**: Intelligent error identification with diagnostic analysis and resolution recommendations

**Monitoring Intelligence**:
- **Progress Prediction**: Intelligent job completion time estimation based on current performance and historical data
- **Performance Analysis**: Real-time performance monitoring with bottleneck identification and optimization suggestions
- **Resource Efficiency**: Usage pattern analysis with efficiency scoring and cost-effectiveness recommendations
- **Issue Detection**: Automated problem identification with diagnostic insights and resolution strategies
- **Trend Analysis**: Performance trend monitoring with predictive maintenance and optimization guidance

**Optimization Insights**:
- **Resource Usage**: Comprehensive analysis of CPU, memory, and I/O utilization with optimization recommendations
- **Performance Optimization**: Bottleneck identification with performance improvement strategies and best practices
- **Cost Analysis**: Resource cost analysis with optimization suggestions for future job submissions
- **Efficiency Scoring**: Job efficiency evaluation with improvement recommendations and best practice guidance

**Prerequisites**: Valid Slurm job ID from previous job submission with cluster access for monitoring
**Tools to use before this**: submit_slurm_job() to get job ID, list_slurm_jobs() for job discovery
**Tools to use after this**: get_job_details() for comprehensive analysis, get_job_output() for results, or cancel_slurm_job() if needed

Use this tool when:
- Monitoring job progress and execution status with intelligent performance analysis ("Check my simulation job performance and optimization opportunities")
- Tracking resource utilization and performance metrics with predictive insights and efficiency recommendations
- Identifying job issues and optimization opportunities with AI-powered diagnostic analysis and resolution strategies
- Analyzing job performance for optimization and efficiency improvement with comprehensive metrics and recommendations
- Monitoring job health and predicting completion times with intelligent analysis and trend monitoring""",
)
async def check_job_status_tool(job_id: str) -> dict:
    """
    Check comprehensive status of a Slurm job with advanced monitoring and intelligent analysis.

    Args:
        job_id: The Slurm job ID to check (required)

    Returns:
        Dictionary containing comprehensive job status with performance insights and optimization recommendations
    """
    try:
        logger.info(
            f"Checking comprehensive status for job: {job_id} with advanced monitoring and intelligent analysis"
        )

        return get_job_status(job_id)
    except Exception as e:
        logger.error(f"Job status check error: {e}")
        return {
            "content": [
                {
                    "text": f'{{"success": false, "error": "{str(e)}", "error_type": "JobStatusError", "troubleshooting": "Verify job ID exists and cluster connectivity"}}'
                }
            ],
            "_meta": {"tool": "check_job_status", "error": "JobStatusError"},
            "isError": True,
        }


@mcp.tool(
    name="cancel_slurm_job",
    description="""Cancel Slurm jobs with intelligent resource cleanup and comprehensive lifecycle management.

This powerful tool provides complete job cancellation capabilities with intelligent resource cleanup, 
impact analysis, and optimization recommendations for efficient cluster resource management and 
workflow optimization.

**Intelligent Job Cancellation Strategy**:
1. **Safe Cancellation**: Comprehensive job termination with graceful shutdown and resource cleanup
2. **Impact Analysis**: Assessment of cancellation impact on dependent jobs and cluster resources
3. **Resource Recovery**: Intelligent resource cleanup with optimization for cluster efficiency
4. **Data Preservation**: Analysis of output preservation and recovery recommendations
5. **Cost Analysis**: Resource usage analysis with cost impact assessment and optimization insights

**Advanced Cancellation Features**:
- **Graceful Termination**: Safe job termination with checkpoint preservation and data integrity
- **Resource Cleanup**: Automatic resource deallocation with cluster optimization and efficiency analysis
- **Impact Assessment**: Analysis of cancellation effects on job dependencies and cluster performance
- **Data Recovery**: Intelligent analysis of recoverable outputs and checkpoint preservation strategies
- **Queue Optimization**: Post-cancellation queue optimization with resource reallocation recommendations

**Optimization Intelligence**:
- **Resource Efficiency**: Analysis of resource recovery and cluster optimization opportunities
- **Cost Impact**: Assessment of cancellation costs and optimization recommendations for future submissions
- **Workflow Analysis**: Impact assessment on dependent jobs with optimization strategies
- **Performance Insights**: Analysis of cancellation reasons with prevention recommendations and best practices

**Prerequisites**: Valid Slurm job ID and appropriate permissions for job cancellation
**Tools to use before this**: check_job_status() to verify job state, get_job_details() for impact analysis
**Tools to use after this**: list_slurm_jobs() to verify cancellation, get_queue_info() for resource reallocation analysis

Use this tool when:
- Canceling problematic jobs with intelligent resource recovery ("Cancel job with resource optimization analysis")
- Terminating jobs that are no longer needed with efficient resource cleanup and cost analysis
- Managing job priorities with intelligent cancellation and resource reallocation strategies
- Optimizing cluster resources through strategic job cancellation and queue management""",
)
async def cancel_slurm_job_tool(job_id: str) -> dict:
    """
    Cancel a Slurm job.

    Args:
        job_id: The Slurm job ID to cancel

    Returns:
        Dictionary with cancellation results
    """
    logger.info(f"Cancelling job: {job_id}")
    return cancel_slurm_job(job_id)


@mcp.tool(
    name="list_slurm_jobs",
    description="""List and analyze Slurm jobs with comprehensive filtering, intelligent analysis, and optimization insights.

This powerful tool provides complete job listing capabilities with sophisticated filtering, intelligent job analysis,
performance metrics, and optimization recommendations for comprehensive cluster workload management and 
workflow optimization.

**Intelligent Job Listing Strategy**:
1. **Comprehensive Discovery**: Advanced job discovery with intelligent filtering and categorization
2. **Performance Analysis**: Job performance evaluation with efficiency metrics and optimization insights
3. **Resource Utilization**: Cluster resource analysis with usage patterns and optimization recommendations
4. **Queue Intelligence**: Queue analysis with scheduling optimization and priority management insights
5. **Workflow Optimization**: Job workflow analysis with dependency tracking and performance optimization

**Advanced Job Listing Features**:
- **Intelligent Filtering**: Sophisticated job filtering by user, state, partition, and resource requirements
- **Performance Metrics**: Job performance analysis with efficiency scoring and optimization recommendations
- **Resource Analytics**: Comprehensive resource utilization analysis with cluster optimization insights
- **Queue Analysis**: Queue position analysis with scheduling optimization and priority recommendations
- **Trend Monitoring**: Job submission and completion trend analysis with workload optimization insights

**Filtering and Analysis Capabilities**:
- **User Filtering**: Filter jobs by specific users with performance analysis and resource usage insights
- **State Analysis**: Job state filtering with transition analysis and optimization recommendations
- **Resource Filtering**: Filter by resource requirements with efficiency analysis and cost optimization
- **Time-Based Analysis**: Historical job analysis with trend identification and performance optimization
- **Partition Intelligence**: Partition-based analysis with load balancing and optimization recommendations

**Optimization Intelligence**:
- **Performance Scoring**: Job efficiency evaluation with improvement recommendations and best practice guidance
- **Resource Optimization**: Cluster resource analysis with optimization strategies and cost-effectiveness insights
- **Queue Optimization**: Queue management insights with scheduling optimization and priority recommendations
- **Workflow Analysis**: Job dependency analysis with workflow optimization and efficiency improvement strategies

**Prerequisites**: Slurm cluster access with job listing permissions and query capabilities
**Tools to use before this**: get_slurm_info() for cluster overview, get_queue_info() for queue analysis
**Tools to use after this**: check_job_status() for specific jobs, get_job_details() for comprehensive analysis

Use this tool when:
- Analyzing job queues and workload patterns with intelligent optimization insights ("Show me all jobs with performance analysis")
- Monitoring cluster utilization and job efficiency with comprehensive metrics and optimization recommendations
- Managing job priorities and resource allocation with intelligent scheduling and queue optimization strategies
- Tracking job performance trends and identifying optimization opportunities with AI-powered analysis and recommendations""",
)
async def list_slurm_jobs_tool(
    user: Optional[str] = None, state: Optional[str] = None
) -> dict:
    """
    List Slurm jobs with optional filtering.

    Args:
        user: Username to filter by (default: current user)
        state: Job state to filter by (PENDING, RUNNING, COMPLETED, etc.)

    Returns:
        Dictionary with list of jobs
    """
    logger.info(f"Listing jobs for user: {user}, state: {state}")
    return list_slurm_jobs(user, state)


@mcp.tool(
    name="get_slurm_info",
    description="""Get comprehensive Slurm cluster information with intelligent analysis and optimization insights.

This powerful tool provides complete cluster analysis by collecting detailed information about cluster configuration,
resource availability, performance metrics, and optimization opportunities with intelligent recommendations for
efficient cluster utilization and workload management.

**Intelligent Cluster Analysis Strategy**:
1. **Comprehensive Discovery**: Complete cluster configuration analysis with intelligent resource assessment
2. **Performance Evaluation**: Cluster performance analysis with efficiency metrics and optimization insights
3. **Resource Intelligence**: Available resource analysis with utilization patterns and optimization recommendations
4. **Capacity Planning**: Cluster capacity analysis with growth prediction and optimization strategies
5. **Health Assessment**: Cluster health monitoring with predictive maintenance and optimization guidance

**Advanced Cluster Information**:
- **Node Configuration**: Detailed node specifications with performance analysis and optimization recommendations
- **Partition Analysis**: Partition configuration with load balancing and scheduling optimization insights
- **Resource Availability**: Real-time resource status with utilization patterns and efficiency recommendations
- **Queue Analytics**: Queue configuration analysis with optimization strategies and performance insights
- **Performance Metrics**: Cluster performance evaluation with bottleneck identification and optimization guidance

**Resource Intelligence Features**:
- **Capacity Analysis**: Comprehensive resource capacity assessment with utilization optimization and efficiency insights
- **Availability Tracking**: Real-time resource availability with intelligent allocation and optimization recommendations
- **Performance Monitoring**: Cluster performance analysis with trend identification and optimization strategies
- **Load Balancing**: Partition load analysis with balancing recommendations and optimization insights
- **Efficiency Scoring**: Cluster efficiency evaluation with improvement recommendations and best practice guidance

**Optimization Intelligence**:
- **Resource Optimization**: Cluster resource optimization with efficiency recommendations and cost-effectiveness analysis
- **Performance Enhancement**: Performance optimization strategies with bottleneck resolution and improvement guidance
- **Capacity Planning**: Intelligent capacity planning with growth prediction and optimization recommendations
- **Cost Analysis**: Resource cost analysis with optimization strategies and efficiency improvement recommendations

**Prerequisites**: Slurm cluster access with cluster information query permissions
**Tools to use before this**: None - this is typically the first tool for cluster assessment
**Tools to use after this**: get_queue_info() for detailed queue analysis, list_slurm_jobs() for workload assessment

Use this tool when:
- Assessing cluster capabilities and resource availability with intelligent analysis ("Show me cluster status with optimization insights")
- Planning job submissions with resource availability analysis and optimization recommendations
- Monitoring cluster health and performance with predictive insights and optimization guidance
- Analyzing cluster efficiency and identifying optimization opportunities with AI-powered recommendations and cost analysis""",
)
async def get_slurm_info_tool() -> dict:
    """
    Get information about the Slurm cluster.

    Args:
        None

    Returns:
        Dictionary with cluster information
    """
    logger.info("Getting Slurm cluster information")
    return get_slurm_info()


@mcp.tool(
    name="get_job_details",
    description="""Get comprehensive Slurm job details with intelligent analysis and performance insights.

This powerful tool provides complete job information analysis by retrieving detailed job specifications,
resource utilization metrics, and performance characteristics with intelligent insights and optimization
recommendations for comprehensive job lifecycle management.

**Intelligent Job Details Analysis**:
1. **Comprehensive Information**: Complete job specification analysis with resource allocation and configuration details
2. **Performance Metrics**: Resource utilization analysis with efficiency scoring and optimization insights
3. **Runtime Analysis**: Job execution analysis with performance trends and bottleneck identification
4. **Resource Efficiency**: Usage pattern analysis with cost optimization and efficiency recommendations
5. **Optimization Insights**: Job performance evaluation with improvement strategies and best practice guidance

**Advanced Job Information**:
- **Job Configuration**: Complete job specifications with resource allocation and parameter analysis
- **Resource Utilization**: CPU, memory, I/O usage with efficiency analysis and optimization recommendations
- **Performance Analysis**: Runtime metrics with throughput analysis and performance optimization insights
- **Queue Analytics**: Job scheduling analysis with queue position and timing optimization insights
- **Cost Analysis**: Resource cost evaluation with efficiency recommendations and optimization strategies

**Optimization Intelligence**:
- **Performance Evaluation**: Job efficiency scoring with improvement recommendations and best practice guidance
- **Resource Optimization**: Usage analysis with cost-effectiveness insights and efficiency improvement strategies
- **Runtime Analysis**: Execution performance evaluation with bottleneck identification and optimization guidance
- **Efficiency Insights**: Resource utilization optimization with cost analysis and performance recommendations

**Prerequisites**: Valid Slurm job ID with appropriate permissions for detailed job information access
**Tools to use before this**: check_job_status() for basic status, submit_slurm_job() for job creation
**Tools to use after this**: get_job_output() for output analysis, optimization tools based on performance insights

Use this tool when:
- Analyzing job performance and resource utilization with comprehensive metrics ("Get detailed job analysis with optimization insights")
- Investigating job efficiency and identifying optimization opportunities with AI-powered recommendations
- Monitoring resource usage patterns for cost optimization and performance improvement strategies
- Evaluating job configurations for future optimization and efficiency enhancement recommendations""",
)
async def get_job_details_tool(job_id: str) -> dict:
    """
    Get detailed information about a Slurm job.

    Args:
        job_id: The Slurm job ID

    Returns:
        Dictionary with detailed job information
    """
    logger.info(f"Getting detailed information for job: {job_id}")
    return get_job_details(job_id)


@mcp.tool(
    name="get_job_output",
    description="""Get comprehensive Slurm job output with intelligent analysis and content organization.

This powerful tool provides complete job output retrieval and analysis by accessing stdout/stderr files
with intelligent content parsing, error detection, and performance insights for comprehensive job
result analysis and troubleshooting.

**Intelligent Output Analysis**:
1. **Content Retrieval**: Complete output file access with intelligent parsing and organization
2. **Error Detection**: Automated error identification with diagnostic analysis and resolution recommendations
3. **Performance Analysis**: Output-based performance evaluation with efficiency insights and optimization guidance
4. **Content Intelligence**: Smart content analysis with pattern recognition and insight extraction
5. **Troubleshooting Insights**: Automated issue identification with diagnostic recommendations and resolution strategies

**Advanced Output Features**:
- **Multi-Output Support**: Comprehensive stdout/stderr access with intelligent content differentiation
- **Error Analysis**: Automated error detection with diagnostic insights and troubleshooting recommendations
- **Performance Metrics**: Output-based performance analysis with efficiency evaluation and optimization insights
- **Content Organization**: Intelligent output formatting with structured presentation and analysis
- **Pattern Recognition**: Smart content analysis with trend identification and insight extraction

**Optimization Intelligence**:
- **Performance Insights**: Output-based performance evaluation with efficiency recommendations and improvement strategies
- **Error Diagnostics**: Intelligent error analysis with resolution strategies and prevention recommendations
- **Content Analysis**: Smart output parsing with pattern recognition and optimization guidance
- **Troubleshooting Intelligence**: Automated issue identification with diagnostic insights and resolution recommendations

**Prerequisites**: Valid Slurm job ID with output files available for analysis
**Tools to use before this**: check_job_status() to verify completion, get_job_details() for job context
**Tools to use after this**: Analysis tools based on output insights, troubleshooting based on error detection

Use this tool when:
- Retrieving job results with intelligent analysis and error detection ("Get job output with performance analysis")
- Troubleshooting job issues with automated error detection and diagnostic recommendations
- Analyzing job performance through output content with efficiency insights and optimization guidance
- Investigating job execution with comprehensive output analysis and intelligent troubleshooting recommendations""",
)
async def get_job_output_tool(job_id: str, output_type: str = "stdout") -> dict:
    """
    Get job output content.

    Args:
        job_id: The Slurm job ID
        output_type: Type of output ("stdout" or "stderr")

    Returns:
        Dictionary with job output content
    """
    logger.info(f"Getting {output_type} for job: {job_id}")
    return get_job_output(job_id, output_type)


@mcp.tool(
    name="get_queue_info",
    description="""Get comprehensive Slurm queue information with intelligent analysis and optimization insights.

This powerful tool provides complete queue analysis by retrieving detailed partition information,
resource availability, and scheduling metrics with intelligent insights and optimization recommendations
for efficient cluster utilization and job planning.

**Intelligent Queue Analysis**:
1. **Queue Intelligence**: Comprehensive queue status analysis with scheduling optimization and performance insights
2. **Resource Availability**: Real-time resource status with utilization patterns and efficiency recommendations
3. **Partition Analysis**: Detailed partition configuration with load balancing and optimization insights
4. **Scheduling Optimization**: Queue scheduling analysis with priority optimization and performance recommendations
5. **Capacity Planning**: Queue capacity analysis with growth prediction and optimization strategies

**Advanced Queue Features**:
- **Multi-Partition Support**: Comprehensive partition analysis with intelligent filtering and comparison
- **Resource Analytics**: Real-time resource availability with utilization analysis and optimization recommendations
- **Scheduling Intelligence**: Queue scheduling optimization with priority analysis and performance insights
- **Load Balancing**: Partition load analysis with balancing recommendations and efficiency optimization
- **Performance Metrics**: Queue performance evaluation with throughput analysis and optimization guidance

**Optimization Intelligence**:
- **Queue Optimization**: Scheduling optimization with efficiency recommendations and performance improvement strategies
- **Resource Planning**: Capacity planning with utilization analysis and optimization recommendations
- **Performance Enhancement**: Queue performance optimization with bottleneck identification and resolution strategies
- **Efficiency Analysis**: Resource efficiency evaluation with cost optimization and utilization improvement guidance

**Prerequisites**: Slurm cluster access with queue information query permissions
**Tools to use before this**: get_slurm_info() for cluster overview, list_slurm_jobs() for workload context
**Tools to use after this**: submit_slurm_job() for optimized job submission, job monitoring tools based on queue insights

Use this tool when:
- Analyzing queue status and resource availability with intelligent optimization insights ("Show queue status with scheduling optimization")
- Planning job submissions with resource availability analysis and partition optimization recommendations
- Monitoring cluster utilization and queue performance with efficiency insights and optimization guidance
- Optimizing job scheduling and resource allocation with AI-powered queue analysis and performance recommendations""",
)
async def get_queue_info_tool(partition: Optional[str] = None) -> dict:
    """
    Get job queue information.

    Args:
        partition: Specific partition to query (optional)

    Returns:
        Dictionary with queue information
    """
    logger.info(f"Getting queue information for partition: {partition}")
    return get_queue_info(partition)


@mcp.tool(
    name="submit_array_job",
    description="""Submit Slurm array jobs with intelligent parallel optimization and comprehensive workflow management.

This powerful tool provides complete array job submission capabilities with intelligent parallel optimization,
resource management, and comprehensive workflow analysis for efficient high-throughput computing and 
parallel workload optimization.

**Intelligent Array Job Strategy**:
1. **Parallel Optimization**: Intelligent parallel task distribution with efficiency analysis and performance optimization
2. **Resource Management**: Comprehensive resource allocation with load balancing and cost optimization
3. **Task Scheduling**: Smart task scheduling with dependency management and performance optimization
4. **Workflow Analysis**: Array job workflow optimization with throughput analysis and efficiency recommendations
5. **Performance Prediction**: Array job performance estimation with bottleneck identification and optimization guidance

**Advanced Array Job Features**:
- **Task Distribution**: Intelligent task distribution with load balancing and parallel optimization
- **Resource Allocation**: Per-task resource optimization with efficiency analysis and cost-effectiveness recommendations
- **Scheduling Intelligence**: Smart array job scheduling with priority optimization and performance analysis
- **Dependency Management**: Task dependency analysis with workflow optimization and efficiency improvements
- **Throughput Optimization**: Array job throughput maximization with resource efficiency and performance optimization

**Parallel Computing Intelligence**:
- **Task Parallelization**: Intelligent task parallelization with efficiency optimization and performance analysis
- **Resource Scaling**: Dynamic resource scaling with cost optimization and performance recommendations
- **Load Balancing**: Task load balancing with cluster optimization and efficiency maximization
- **Performance Analytics**: Parallel performance analysis with bottleneck identification and optimization strategies
- **Efficiency Scoring**: Array job efficiency evaluation with improvement recommendations and best practice guidance

**Optimization Intelligence**:
- **Throughput Maximization**: Array job throughput optimization with resource efficiency and cost-effectiveness analysis
- **Resource Efficiency**: Per-task resource optimization with utilization analysis and cost optimization
- **Performance Optimization**: Parallel performance optimization with bottleneck resolution and efficiency improvements
- **Cost Analysis**: Array job cost analysis with optimization strategies and efficiency recommendations

**Prerequisites**: Valid script file and Slurm cluster access with array job submission capabilities
**Tools to use before this**: get_slurm_info() for cluster assessment, get_queue_info() for resource planning
**Tools to use after this**: check_job_status() for monitoring, list_slurm_jobs() for array job tracking

Use this tool when:
- Running high-throughput parallel computations with intelligent resource optimization ("Submit array job with parallel optimization")
- Processing large datasets with parallel efficiency and cost optimization
- Executing parameter sweeps with intelligent task distribution and performance optimization
- Managing parallel workflows with comprehensive resource allocation and efficiency analysis""",
)
async def submit_array_job_tool(
    script_path: str,
    array_range: str,
    cores: int = 1,
    memory: str = "1GB",
    time_limit: str = "01:00:00",
    job_name: Optional[str] = None,
    partition: Optional[str] = None,
) -> dict:
    """
    Submit an array job to Slurm scheduler.

    Args:
        script_path: Path to the job script file
        array_range: Array range specification (e.g., "1-10", "1-100:2")
        cores: Number of cores per array task (default: 1)
        memory: Memory per array task (default: "1GB")
        time_limit: Time limit per array task in HH:MM:SS format (default: "01:00:00")
        job_name: Base name for the array job (default: derived from script)
        partition: Slurm partition to use (default: system default)

    Returns:
        Dictionary with array job submission results
    """
    logger.info(
        f"Submitting array job: {script_path}, range: {array_range}, cores: {cores}"
    )
    return submit_array_job(
        script_path, array_range, cores, memory, time_limit, job_name, partition
    )


@mcp.tool(
    name="get_node_info",
    description="""Get comprehensive Slurm node information with intelligent analysis and resource optimization insights.

This powerful tool provides complete node analysis by retrieving detailed node specifications,
resource availability, and performance characteristics with intelligent insights and optimization
recommendations for efficient cluster resource management and allocation planning.

**Intelligent Node Analysis**:
1. **Node Discovery**: Comprehensive node configuration analysis with resource assessment and availability tracking
2. **Resource Intelligence**: Node resource analysis with utilization patterns and efficiency recommendations
3. **Performance Evaluation**: Node performance analysis with efficiency metrics and optimization insights
4. **Availability Analysis**: Real-time node availability assessment with allocation optimization recommendations
5. **Health Monitoring**: Node health assessment with predictive maintenance and optimization guidance

**Advanced Node Features**:
- **Multi-Node Analysis**: Comprehensive node cluster analysis with intelligent comparison and optimization
- **Resource Analytics**: Node resource utilization with efficiency analysis and allocation recommendations
- **Performance Metrics**: Node performance evaluation with throughput analysis and optimization insights
- **Availability Intelligence**: Real-time availability tracking with optimal allocation strategies
- **Health Assessment**: Node health monitoring with predictive maintenance and efficiency optimization

**Optimization Intelligence**:
- **Resource Optimization**: Node resource allocation optimization with efficiency recommendations and cost analysis
- **Performance Enhancement**: Node performance optimization with bottleneck identification and resolution strategies
- **Allocation Planning**: Intelligent node allocation planning with resource optimization and efficiency insights
- **Capacity Analysis**: Node capacity evaluation with utilization optimization and growth planning recommendations

**Prerequisites**: Slurm cluster access with node information query permissions
**Tools to use before this**: get_slurm_info() for cluster overview, get_queue_info() for resource context
**Tools to use after this**: allocate_slurm_nodes() for node allocation, job submission tools based on node availability

Use this tool when:
- Analyzing node resources and availability with intelligent optimization insights ("Show node status with resource optimization")
- Planning resource allocation with node availability analysis and optimization recommendations
- Monitoring cluster hardware and node performance with efficiency insights and optimization guidance
- Optimizing resource utilization and node allocation with AI-powered analysis and performance recommendations""",
)
async def get_node_info_tool() -> dict:
    """
    Get cluster node information.

    Args:
        None

    Returns:
        Dictionary with node information
    """
    logger.info("Getting cluster node information")
    return get_node_info()


@mcp.tool(
    name="allocate_slurm_nodes",
    description="""Allocate Slurm nodes with intelligent resource optimization and comprehensive interactive session management.

This powerful tool provides complete node allocation capabilities using salloc for interactive sessions and resource
reservation with intelligent resource optimization, performance analysis, and comprehensive allocation management for
efficient cluster utilization and interactive workload optimization.

**Intelligent Node Allocation Strategy**:
1. **Resource Optimization**: Intelligent resource allocation with efficiency analysis and cost optimization
2. **Availability Analysis**: Real-time node availability assessment with optimal allocation recommendations
3. **Performance Prediction**: Allocation performance estimation with optimization insights and efficiency analysis
4. **Interactive Management**: Comprehensive interactive session management with resource monitoring and optimization
5. **Efficiency Optimization**: Resource utilization optimization with cost-effectiveness analysis and performance insights

**Advanced Allocation Features**:
- **Smart Resource Selection**: Intelligent node selection based on workload requirements and cluster optimization
- **Interactive Session Management**: Comprehensive session lifecycle management with performance monitoring and optimization
- **Resource Efficiency**: Allocation efficiency analysis with cost optimization and utilization recommendations
- **Performance Monitoring**: Real-time allocation performance tracking with optimization insights and efficiency analysis
- **Availability Intelligence**: Node availability analysis with optimal timing recommendations and resource optimization

**Optimization Intelligence**:
- **Resource Sizing**: Intelligent resource recommendation based on workload analysis and historical performance data
- **Node Selection**: Optimal node selection with performance analysis and efficiency optimization
- **Cost Optimization**: Resource allocation cost analysis with efficiency recommendations and optimization strategies
- **Performance Prediction**: Allocation performance estimation with bottleneck identification and optimization guidance
- **Utilization Analysis**: Resource utilization analysis with efficiency scoring and optimization recommendations

**Interactive Session Intelligence**:
- **Session Optimization**: Interactive session performance optimization with resource efficiency and cost analysis
- **Resource Monitoring**: Real-time resource usage monitoring with optimization insights and efficiency recommendations
- **Performance Analytics**: Session performance analysis with bottleneck identification and optimization strategies
- **Efficiency Tracking**: Resource efficiency monitoring with optimization recommendations and cost-effectiveness analysis

**Prerequisites**: Slurm cluster access with node allocation permissions and interactive session capabilities
**Tools to use before this**: get_slurm_info() for cluster assessment, get_node_info() for availability analysis
**Tools to use after this**: get_allocation_status() for monitoring, deallocate_slurm_nodes() for cleanup

Use this tool when:
- Creating interactive computing sessions with optimized resource allocation ("Allocate nodes for interactive analysis with performance optimization")
- Reserving cluster resources for interactive workloads with intelligent resource management and cost optimization
- Setting up development environments with optimal resource allocation and efficiency monitoring
- Managing interactive sessions with comprehensive performance analysis and optimization recommendations""",
)
async def allocate_slurm_nodes_tool(
    nodes: int = 1,
    cores: int = 1,
    memory: Optional[str] = None,
    time_limit: str = "01:00:00",
    partition: Optional[str] = None,
    job_name: Optional[str] = None,
    immediate: bool = False,
) -> dict:
    """
    Allocate Slurm nodes using salloc command.

    Args:
        nodes: Number of nodes to allocate (default: 1)
        cores: Number of cores per node (default: 1)
        memory: Memory requirement (e.g., "4G", "2048M")
        time_limit: Time limit (e.g., "1:00:00", default: "01:00:00")
        partition: Slurm partition to use
        job_name: Name for the allocation
        immediate: Whether to return immediately without waiting for allocation

    Returns:
        Dictionary with allocation information
    """
    logger.info(f"Allocating {nodes} nodes with {cores} cores each")
    return allocate_nodes(
        nodes, cores, memory, time_limit, partition, job_name, immediate
    )


@mcp.tool(
    name="deallocate_slurm_nodes",
    description="""Deallocate Slurm nodes with intelligent resource cleanup and optimization analysis.

This powerful tool provides complete node deallocation capabilities with intelligent resource cleanup,
impact analysis, and optimization recommendations for efficient cluster resource management and
allocation lifecycle optimization.

**Intelligent Deallocation Strategy**:
1. **Safe Deallocation**: Comprehensive allocation termination with resource cleanup and optimization
2. **Impact Analysis**: Assessment of deallocation impact on cluster resources and performance
3. **Resource Recovery**: Intelligent resource cleanup with cluster optimization and efficiency analysis
4. **Data Preservation**: Analysis of session data preservation and recovery recommendations
5. **Optimization Insights**: Resource usage analysis with efficiency recommendations and cost optimization

**Advanced Deallocation Features**:
- **Graceful Termination**: Safe allocation termination with session preservation and data integrity
- **Resource Cleanup**: Automatic resource recovery with cluster optimization and efficiency analysis
- **Impact Assessment**: Analysis of deallocation effects on cluster performance and resource availability
- **Session Recovery**: Intelligent analysis of recoverable session data and checkpoint preservation strategies
- **Queue Optimization**: Post-deallocation queue optimization with resource reallocation recommendations

**Optimization Intelligence**:
- **Resource Efficiency**: Analysis of resource recovery and cluster optimization opportunities
- **Cost Impact**: Assessment of allocation costs with optimization recommendations for future allocations
- **Performance Insights**: Analysis of allocation usage with efficiency recommendations and best practices
- **Utilization Analysis**: Resource utilization evaluation with optimization guidance and efficiency improvements

**Prerequisites**: Valid allocation ID and appropriate permissions for node deallocation
**Tools to use before this**: get_allocation_status() to verify allocation state, allocate_slurm_nodes() for allocation context
**Tools to use after this**: get_node_info() to verify resource recovery, optimization tools based on usage analysis

Use this tool when:
- Cleaning up completed interactive sessions with intelligent resource recovery ("Deallocate nodes with resource optimization")
- Terminating allocations that are no longer needed with efficient resource cleanup and cost analysis
- Managing allocation lifecycle with intelligent resource management and optimization strategies
- Optimizing cluster resources through strategic allocation cleanup and resource reallocation""",
)
async def deallocate_slurm_nodes_tool(allocation_id: str) -> dict:
    """
    Deallocate Slurm nodes by canceling the allocation.

    Args:
        allocation_id: The allocation ID to cancel

    Returns:
        Dictionary with deallocation status
    """
    logger.info(f"Deallocating allocation {allocation_id}")
    return deallocate_nodes(allocation_id)


@mcp.tool(
    name="get_allocation_status",
    description="""Get comprehensive Slurm allocation status with intelligent monitoring and performance insights.

This powerful tool provides complete allocation status analysis by retrieving detailed allocation information,
resource utilization metrics, and performance characteristics with intelligent insights and optimization
recommendations for efficient interactive session management.

**Intelligent Allocation Monitoring**:
1. **Status Analysis**: Comprehensive allocation status tracking with performance analysis and trend monitoring
2. **Resource Monitoring**: Real-time resource utilization analysis with efficiency metrics and optimization insights
3. **Performance Analytics**: Allocation performance evaluation with efficiency scoring and optimization recommendations
4. **Usage Intelligence**: Resource usage pattern analysis with cost optimization and efficiency recommendations
5. **Optimization Insights**: Allocation efficiency evaluation with improvement strategies and best practice guidance

**Advanced Allocation Status**:
- **Real-Time Monitoring**: Comprehensive allocation tracking with performance analysis and resource utilization insights
- **Resource Analytics**: CPU, memory, node usage with efficiency analysis and optimization recommendations
- **Performance Metrics**: Allocation performance evaluation with throughput analysis and optimization insights
- **Usage Patterns**: Resource consumption analysis with efficiency scoring and cost optimization recommendations
- **Health Assessment**: Allocation health monitoring with issue detection and optimization guidance

**Optimization Intelligence**:
- **Performance Evaluation**: Allocation efficiency scoring with improvement recommendations and best practice guidance
- **Resource Optimization**: Usage analysis with cost-effectiveness insights and efficiency improvement strategies
- **Utilization Analysis**: Resource consumption evaluation with optimization recommendations and efficiency insights
- **Cost Analysis**: Allocation cost evaluation with optimization strategies and efficiency improvement recommendations

**Prerequisites**: Valid allocation ID with appropriate permissions for allocation status monitoring
**Tools to use before this**: allocate_slurm_nodes() for allocation creation, get_node_info() for resource context
**Tools to use after this**: Resource optimization based on status insights, deallocate_slurm_nodes() for cleanup

Use this tool when:
- Monitoring allocation performance and resource utilization with intelligent analysis ("Check allocation status with performance insights")
- Tracking interactive session efficiency with optimization recommendations and cost analysis
- Analyzing allocation usage patterns for optimization and efficiency improvement strategies
- Managing allocation lifecycle with comprehensive monitoring and intelligent optimization guidance""",
)
async def get_allocation_status_tool(allocation_id: str) -> dict:
    """
    Get status of a node allocation.

    Args:
        allocation_id: The allocation ID to check

    Returns:
        Dictionary with allocation status information
    """
    logger.info(f"Checking status of allocation {allocation_id}")
    return get_allocation_status(allocation_id)


def main():
    """
    Main entry point to start the FastMCP server using the specified transport.
    Chooses between stdio and SSE based on command-line arguments or environment variables.
    """
    import argparse

    # Handle 'help' command (without dashes) by converting to --help
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        sys.argv[1] = "--help"

    parser = argparse.ArgumentParser(
        description="Slurm MCP Server - Comprehensive HPC job management server with intelligent optimization",
        prog="slurm-mcp",
    )
    parser.add_argument(
        "--version", action="version", version="Slurm MCP Server v0.1.0"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type to use (default: stdio)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for SSE transport (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for SSE transport (default: 8000)"
    )

    args = parser.parse_args()

    try:
        logger.info("Starting Slurm MCP Server")

        # Use command-line args or environment variables
        transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio").lower()

        if transport == "sse":
            # SSE transport for web-based clients
            host = args.host or os.getenv("MCP_SSE_HOST", "0.0.0.0")
            port = args.port or int(os.getenv("MCP_SSE_PORT", "8000"))
            logger.info(f"Starting SSE transport on {host}:{port}")
            print(
                f"Starting Slurm MCP Job Management Server on {host}:{port}",
                file=sys.stderr,
            )
            mcp.run(transport="sse", host=host, port=port)
        else:
            # Default stdio transport
            logger.info("Starting stdio transport")
            print(
                "Starting Slurm MCP Job Management Server with stdio transport",
                file=sys.stderr,
            )
            mcp.run(transport="stdio")

    except Exception as e:
        logger.error(f"Server error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

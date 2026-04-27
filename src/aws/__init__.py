"""
AWS Integration Module

This module provides comprehensive AWS service integration for the SynthaTrial platform,
designed for meaningful cloud-native architecture and competition demonstration.

Components:
- S3GenomicDataManager: VCF file storage and retrieval
- S3ReportManager: PDF S3 upload disabled (stubs only; reports are download-only in-app)
- LambdaBatchProcessor: Parallel processing for large cohorts
- StepFunctionsOrchestrator: Clinical trial workflow orchestration
"""

__version__ = "0.4.0"
__author__ = "SynthaTrial Team"

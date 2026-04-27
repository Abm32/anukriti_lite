"""
Architecture Diagram Generation Module

This module provides programmatic generation of professional architecture diagrams
for the SynthaTrial platform, optimized for AWS AI competition presentation.

Features:
- AWS service icons and professional styling
- Multiple output formats (SVG, PNG)
- Configurable resolution and color schemes
- Competition-ready visual communication
"""

import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path

try:
    from diagrams import Diagram, Cluster, Edge
    from diagrams.aws.compute import EC2, Lambda
    from diagrams.aws.storage import S3
    from diagrams.aws.integration import StepFunctions
    from diagrams.aws.ml import Bedrock
    from diagrams.aws.management import Cloudwatch
    from diagrams.aws.security import SecretsManager
    from diagrams.aws.network import APIGateway
    from diagrams.onprem.client import Users
    from diagrams.programming.framework import FastAPI
    from diagrams.programming.language import Python
    DIAGRAMS_AVAILABLE = True
except ImportError as e:
    DIAGRAMS_AVAILABLE = False
    print(f"Warning: diagrams library not available. Error: {e}")
    print("Install with: pip install diagrams")


class DiagramConfig:
    """Configuration for architecture diagram generation"""
    
    def __init__(
        self,
        title: str = "SynthaTrial Architecture",
        output_format: str = "svg",
        resolution: Tuple[int, int] = (1920, 1080),
        color_scheme: str = "competition",
        show_data_flow: bool = True,
        include_aws_icons: bool = True
    ):
        self.title = title
        self.output_format = output_format.lower()
        self.resolution = resolution
        self.color_scheme = color_scheme
        self.show_data_flow = show_data_flow
        self.include_aws_icons = include_aws_icons
        
        # Color schemes
        self.color_schemes = {
            "competition": {
                "aws_services": "#FF9900",  # AWS Orange
                "core_pgx": "#00C851",      # Green
                "llm_ai": "#FF6B35",        # Orange
                "data_flow": "#007BFF",     # Blue
                "background": "#FFFFFF"     # White
            },
            "default": {
                "aws_services": "#232F3E",  # AWS Dark Blue
                "core_pgx": "#146EB4",      # Blue
                "llm_ai": "#FF9900",        # Orange
                "data_flow": "#666666",     # Gray
                "background": "#FFFFFF"     # White
            }
        }


class DiagramGenerator:
    """Professional architecture diagram generator for SynthaTrial platform"""
    
    def __init__(self, config: Optional[DiagramConfig] = None):
        if not DIAGRAMS_AVAILABLE:
            raise ImportError("diagrams library is required. Install with: pip install diagrams")
        
        self.config = config or DiagramConfig()
        self.output_dir = Path("docs")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_main_architecture(self, filename: str = "architecture") -> str:
        """Generate the main system architecture diagram"""
        
        # The diagrams library generates PNG by default
        output_path = self.output_dir / f"{filename}.png"
        
        # Configure diagram attributes
        graph_attr = {
            "fontsize": "16",
            "fontname": "Arial",
            "bgcolor": self.config.color_schemes[self.config.color_scheme]["background"],
            "rankdir": "TB",
            "splines": "ortho"
        }
        
        with Diagram(
            self.config.title,
            filename=str(output_path.with_suffix("")),
            graph_attr=graph_attr,
            show=False
        ):
            # User Interface Layer
            with Cluster("User Interface Layer"):
                users = Users("Users/Judges")
                streamlit_ui = Python("Streamlit UI\n(Interactive)")
                fastapi_rest = FastAPI("FastAPI REST\n(API)")
                demo_portal = Python("Demo Portal\n(Competition)")
            
            # AWS Integration Layer
            with Cluster("AWS Integration Layer"):
                api_gateway = APIGateway("API Gateway\n(Routing)")
                cloudwatch = Cloudwatch("Cloudwatch\n(Monitoring)")
                secrets_mgr = SecretsManager("Secrets Manager\n(Credentials)")
            
            # Core Processing Layer
            with Cluster("Core Processing Layer (EC2)"):
                with Cluster("Deterministic PGx Engine"):
                    vcf_processor = Python("VCF\nProcessor")
                    variant_lookup = Python("Variant\nLookup DB")
                    allele_caller = Python("Allele Caller\n(CPIC/PharmVar)")
                
                with Cluster("Population Simulator (NEW)"):
                    cohort_gen = Python("Cohort\nGenerator")
                    parallel_proc = Python("Parallel\nProcessor")
                    aggregation = Python("Aggregation\nEngine")
            
            # AWS Services Layer
            with Cluster("AWS Services Layer"):
                s3_vcf = S3("S3 Bucket\n(VCF Data)")
                s3_reports = S3("S3 Bucket\n(PDF Reports)")
                lambda_batch = Lambda("Lambda\n(Batch Sim)")
                step_functions = StepFunctions("Step Functions\n(Trial Orchestration)")
                bedrock_llm = Bedrock("Bedrock\n(Claude 3)")
            
            # Data flow connections
            if self.config.show_data_flow:
                # User interactions
                users >> Edge(label="Web UI") >> streamlit_ui
                users >> Edge(label="API") >> fastapi_rest
                users >> Edge(label="Demo") >> demo_portal
                
                # API routing
                [streamlit_ui, fastapi_rest, demo_portal] >> api_gateway
                api_gateway >> cloudwatch
                
                # Core processing flow
                api_gateway >> vcf_processor
                vcf_processor >> variant_lookup >> allele_caller
                
                # Population simulation flow
                allele_caller >> cohort_gen
                cohort_gen >> parallel_proc >> aggregation
                
                # AWS service integration
                vcf_processor >> s3_vcf
                aggregation >> s3_reports
                parallel_proc >> lambda_batch
                cohort_gen >> step_functions
                allele_caller >> bedrock_llm
                
                # Monitoring
                [s3_vcf, s3_reports, lambda_batch, step_functions, bedrock_llm] >> cloudwatch
        
        return str(output_path)
    
    def generate_aws_integration_diagram(self, filename: str = "aws_integration") -> str:
        """Generate detailed AWS service integration diagram"""
        
        output_path = self.output_dir / f"{filename}.png"
        
        with Diagram(
            "AWS Service Integration",
            filename=str(output_path.with_suffix("")),
            show=False
        ):
            # Core Application
            with Cluster("SynthaTrial Core"):
                app = Python("Application")
            
            # S3 Integration
            with Cluster("S3 Storage"):
                s3_genomic = S3("Genomic Data\n(VCF Files)")
                s3_reports = S3("PDF Reports\n(Lifecycle)")
            
            # Compute Integration
            with Cluster("Compute Services"):
                lambda_func = Lambda("Batch Processor\n(Parallel)")
                step_func = StepFunctions("Trial Orchestrator\n(Workflow)")
            
            # AI/ML Integration
            with Cluster("AI/ML Services"):
                bedrock = Bedrock("Claude 3\n(Explanation)")
            
            # Monitoring & Security
            with Cluster("Management"):
                cloudwatch = Cloudwatch("Logging &\nMetrics")
                secrets = SecretsManager("Credentials")
            
            # Connections
            app >> Edge(label="Upload/Download") >> s3_genomic
            app >> Edge(label="Store Reports") >> s3_reports
            app >> Edge(label="Invoke Batch") >> lambda_func
            app >> Edge(label="Start Workflow") >> step_func
            app >> Edge(label="LLM Requests") >> bedrock
            
            [s3_genomic, s3_reports, lambda_func, step_func, bedrock] >> cloudwatch
            app >> secrets
        
        return str(output_path)
    
    def generate_population_simulation_diagram(self, filename: str = "population_simulation") -> str:
        """Generate population simulation architecture diagram"""
        
        output_path = self.output_dir / f"{filename}.png"
        
        with Diagram(
            "Population Simulation Architecture",
            filename=str(output_path.with_suffix("")),
            show=False
        ):
            # Input
            users = Users("Researchers")
            
            # Population Simulator
            with Cluster("Population Simulator"):
                cohort_gen = Python("Cohort Generator\n(Diverse Populations)")
                parallel_proc = Python("Parallel Processor\n(Batch Processing)")
                metrics = Python("Metrics Engine\n(Real-time)")
            
            # AWS Scaling
            with Cluster("AWS Scaling"):
                lambda_batch = Lambda("Lambda Functions\n(10,000+ patients)")
                step_functions = StepFunctions("Orchestration\n(Workflow)")
            
            # Storage & Results
            with Cluster("Results & Analytics"):
                s3_results = S3("Simulation Results")
                analytics = Python("Analytics Dashboard\n(Visualizations)")
            
            # Monitoring
            monitoring = Cloudwatch("Performance\nMonitoring")
            
            # Flow
            users >> cohort_gen
            cohort_gen >> parallel_proc
            parallel_proc >> lambda_batch
            lambda_batch >> step_functions
            step_functions >> s3_results
            s3_results >> analytics
            
            [parallel_proc, lambda_batch, step_functions] >> metrics
            metrics >> monitoring
        
        return str(output_path)
    
    def generate_all_diagrams(self) -> Dict[str, str]:
        """Generate all architecture diagrams"""
        
        diagrams = {}
        
        try:
            # Main architecture
            diagrams["main"] = self.generate_main_architecture()
            print(f"✓ Generated main architecture diagram: {diagrams['main']}")
            
            # AWS integration
            diagrams["aws"] = self.generate_aws_integration_diagram()
            print(f"✓ Generated AWS integration diagram: {diagrams['aws']}")
            
            # Population simulation
            diagrams["population"] = self.generate_population_simulation_diagram()
            print(f"✓ Generated population simulation diagram: {diagrams['population']}")
            
        except Exception as e:
            print(f"Error generating diagrams: {e}")
            raise
        
        return diagrams
    
    def generate_readme_embedded_version(self, diagram_path: str, max_width: int = 800) -> str:
        """Generate README-embedded version with proper sizing"""
        
        if not os.path.exists(diagram_path):
            raise FileNotFoundError(f"Diagram not found: {diagram_path}")
        
        # For SVG, we can embed directly with size constraints
        if diagram_path.endswith('.svg'):
            return f'<img src="{diagram_path}" alt="Architecture Diagram" width="{max_width}" />'
        else:
            return f'![Architecture Diagram]({diagram_path})'
    
    def validate_output(self, diagram_path: str) -> bool:
        """Validate that diagram was generated successfully"""
        
        if not os.path.exists(diagram_path):
            return False
        
        # Check file size (should be > 0)
        if os.path.getsize(diagram_path) == 0:
            return False
        
        return True


def main():
    """Main function for CLI usage"""
    
    if not DIAGRAMS_AVAILABLE:
        print("Error: diagrams library not installed")
        print("Install with: pip install diagrams")
        return
    
    # Create generator with competition configuration
    config = DiagramConfig(
        title="SynthaTrial: AWS AI Competition Architecture",
        output_format="svg",
        color_scheme="competition"
    )
    
    generator = DiagramGenerator(config)
    
    print("Generating architecture diagrams...")
    diagrams = generator.generate_all_diagrams()
    
    print("\nValidating outputs...")
    for name, path in diagrams.items():
        if generator.validate_output(path):
            print(f"✓ {name}: {path}")
        else:
            print(f"✗ {name}: Failed to generate {path}")
    
    print(f"\nDiagrams generated in: {generator.output_dir}")
    print("Ready for README embedding and competition presentation!")


if __name__ == "__main__":
    main()
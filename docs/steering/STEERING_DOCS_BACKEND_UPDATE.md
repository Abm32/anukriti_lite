# Steering Documentation Update - Dual LLM Backend Support

## Date: February 17, 2026

## Overview
This document summarizes the updates made to the steering documentation files to reflect the new dual LLM backend architecture supporting both Google Gemini and AWS Bedrock, along with associated new features and dependencies.

## Recent Changes Context
Based on the recent commit "Update Streamlit UI with minimalistic design and modernize app interface" and associated code changes, the platform now supports:

1. **Dual LLM Backend Architecture**: Gemini (default) and Bedrock (AWS)
2. **New Dependencies**: boto3, numpy, reportlab
3. **New Source Modules**: Bedrock integration, RAG system, structured output
4. **Enhanced UI**: Backend selector, per-request override
5. **Enhanced API**: Backend selection, structured output, PDF reports

## Files Updated

### 1. `.kiro/steering/tech.md`

#### Core Technologies Section
**Added:** AWS Bedrock as alternative LLM backend:
```
- **AWS Bedrock** - Alternative LLM backend with Claude 3 Haiku and Titan embeddings for pharmacogenomics analysis (optional)
```

**Updated:** LangChain description to mention dual backend support:
```
- **LangChain** - LLM integration framework with enhanced RAG capabilities supporting both Gemini and Bedrock backends
```

#### Core Dependencies Section
**Added:** New dependencies:
- `boto3>=1.34.0` - AWS SDK for Bedrock integration
- `numpy>=1.24.0` - Numerical computing for embeddings
- `reportlab>=4.4.0` - PDF report generation

#### Environment Variables Section
**Completely Updated:** New comprehensive environment configuration:
- **LLM Backend Selection**: `LLM_BACKEND=gemini|bedrock`
- **Gemini Configuration**: Existing variables with better organization
- **Bedrock Configuration**: New AWS-specific variables
  - AWS credentials (access key, secret key, or IAM role)
  - Bedrock region configuration
  - Claude model selection
  - Titan embeddings model selection

#### Enhanced Streamlit UI Features Section
**Added:** New UI capabilities:
- LLM Backend selector: Choose between Gemini (Google) or Bedrock (AWS) per session
- Per-request backend override capability

#### Architecture Notes Section
**Added:** New architecture components:
- **Enhanced LLM prompting**: Multi-model support (Gemini and Bedrock backends)
- **Dual LLM Backend Support**: Per-request backend selection

### 2. `.kiro/steering/product.md`

#### Core Functionality Section
**Updated:** AI Simulation description:
```
- **AI Simulation**: Uses Google Gemini LLM (gemini-2.5-flash default) or AWS Bedrock (Claude 3 Haiku) with enhanced RAG and CPIC guideline-based prompting to predict drug responses using structural analysis. Supports per-request backend selection for flexible deployment.
```

**Updated:** Modern Web Interface description:
```
- **Modern Web Interface**: ... LLM backend selector (Gemini/Bedrock), per-request backend override, and competition-ready demo features with configurable API URL
```

### 3. `.kiro/steering/structure.md`

#### Core Modules Section
**Added:** New Bedrock-related modules:
- **`llm_bedrock.py`**: AWS Bedrock LLM integration using Claude 3 models
- **`embeddings_bedrock.py`**: AWS Bedrock Titan embeddings integration
- **`rag_bedrock.py`**: Bedrock-based RAG implementation with local CPIC retrieval
- **`rag/`**: RAG system components for document retrieval and context generation
- **`pgx_structured.py`**: Structured pharmacogenomics output formatting and confidence scoring
- **`report_pdf.py`**: PDF report generation for analysis results

#### Entry Points Section
**Updated:** app.py description:
```
... LLM backend selector (Gemini/Bedrock), per-request backend override capability, and sidebar collapsed by default for cleaner main interface.
```

**Updated:** api.py description:
```
- **`api.py`**: FastAPI REST API wrapper providing health check, analysis, and demo endpoints for programmatic access and cloud deployment. Supports dual LLM backends (Gemini/Bedrock) with per-request backend override, batch processing, structured PGx output, and PDF report generation.
```

## Key Features Added

### 1. Dual LLM Backend Architecture
- **Default**: Google Gemini (gemini-2.5-flash)
- **Alternative**: AWS Bedrock (Claude 3 Haiku + Titan embeddings)
- **Configuration**: `LLM_BACKEND=gemini|bedrock`
- **Per-request override**: API supports backend selection per request

### 2. Enhanced User Interface
- **Backend Selector**: Radio button in sidebar to choose Gemini or Bedrock
- **Real-time Status**: Shows current backend and model in system status
- **Per-session Override**: UI choice overrides server default per request

### 3. Enhanced API Capabilities
- **Backend Parameter**: `llm_backend` field in API requests
- **Structured Output**: Enhanced PGx output formatting
- **PDF Reports**: Downloadable analysis reports
- **Batch Processing**: Backend selection for batch operations

### 4. New Dependencies and Modules
- **boto3**: AWS SDK for Bedrock integration
- **numpy**: Numerical computing for embeddings
- **reportlab**: PDF report generation
- **RAG System**: Document retrieval and context generation
- **Bedrock Integration**: Complete AWS Bedrock LLM pipeline

### 5. Configuration Flexibility
- **Environment-based**: Set default backend via `LLM_BACKEND`
- **Request-based**: Override backend per API request
- **Session-based**: UI allows per-session backend selection
- **Credential Management**: Support for AWS credentials or IAM roles

## Technical Implementation Details

### Backend Selection Logic
1. **Server Default**: Set via `LLM_BACKEND` environment variable
2. **Request Override**: API `llm_backend` parameter overrides server default
3. **UI Integration**: Streamlit sends backend choice with each request
4. **Fallback**: Invalid backend selections fall back to server default

### AWS Bedrock Integration
- **Models**: Claude 3 Haiku for text generation
- **Embeddings**: Titan Embed Text v2 for vector similarity
- **Region**: Configurable (default: us-east-1)
- **Authentication**: AWS credentials or IAM role (EC2)

### Structured Output Enhancement
- **Confidence Scoring**: Enhanced risk assessment with confidence metrics
- **PDF Generation**: Professional reports with ReportLab
- **Structured Data**: JSON-formatted PGx results for integration

## Impact Assessment

### For Users
- **Choice**: Can select preferred LLM backend (Gemini vs Bedrock)
- **Flexibility**: Per-session backend selection in UI
- **Transparency**: Clear indication of which backend is being used
- **Enhanced Output**: Structured results and PDF reports

### For Developers
- **Architecture**: Clean separation between backend implementations
- **Configuration**: Flexible environment-based configuration
- **API**: Enhanced API with backend selection capabilities
- **Integration**: Easy to add additional LLM backends in future

### For Deployment
- **Cloud Agnostic**: Support for both Google Cloud (Gemini) and AWS (Bedrock)
- **Cost Optimization**: Can choose backend based on cost/performance needs
- **Compliance**: AWS Bedrock may be preferred for certain compliance requirements
- **Redundancy**: Fallback options if one backend is unavailable

## Validation

All updates have been validated against:
✅ Recent commit changes in api.py, app.py, src/config.py
✅ New source files: llm_bedrock.py, embeddings_bedrock.py, rag_bedrock.py
✅ Updated requirements.txt with new dependencies
✅ UI changes for backend selection
✅ API changes for per-request backend override

## Configuration Examples

### Gemini Backend (Default)
```bash
LLM_BACKEND=gemini
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

### Bedrock Backend
```bash
LLM_BACKEND=bedrock
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
BEDROCK_REGION=us-east-1
CLAUDE_MODEL=anthropic.claude-3-haiku-20240307-v1:0
```

### Per-Request Override (API)
```json
{
  "drug_name": "Warfarin",
  "patient_profile": "...",
  "llm_backend": "bedrock"
}
```

## Future Enhancements

The dual backend architecture enables:
- **Additional Backends**: Easy to add OpenAI, Anthropic direct, etc.
- **Load Balancing**: Distribute requests across backends
- **A/B Testing**: Compare backend performance
- **Cost Optimization**: Route requests based on cost/performance
- **Compliance**: Use specific backends for regulatory requirements

## Conclusion

The steering documentation has been successfully updated to reflect the new dual LLM backend architecture. The platform now supports both Google Gemini and AWS Bedrock with:

- **Flexible Configuration**: Environment, request, and session-level backend selection
- **Enhanced UI**: Backend selector with real-time status
- **Robust API**: Per-request backend override with structured output
- **Complete Integration**: New dependencies, modules, and features documented
- **Production Ready**: Full AWS Bedrock integration with proper authentication

This architecture provides users with choice, developers with flexibility, and deployments with cloud-agnostic options while maintaining backward compatibility with existing Gemini-based deployments.

---

**Document Version:** 1.0
**Last Updated:** February 17, 2026
**Updated By:** Kiro AI Assistant
**Review Status:** Ready for Review
**Related Changes:** Commit 486794e - "Update Streamlit UI with minimalistic design and modernize app interface"

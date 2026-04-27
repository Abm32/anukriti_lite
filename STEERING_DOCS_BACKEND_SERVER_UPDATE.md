# Steering Documentation Update: Backend Server Requirements

## Summary

Updated all steering documentation files (`.kiro/steering/tech.md`, `.kiro/steering/product.md`, `.kiro/steering/structure.md`) to reflect critical backend server setup requirements and troubleshooting guidance based on recent user experience.

## Key Updates Made

### 1. Environment Setup Requirements (tech.md)

**Updated Installation Section:**
- Changed environment name from `anukriti` to `synthatrial` (matching actual setup)
- Added critical note about conda environment activation
- Updated to use `pip install -r requirements.txt` for complete dependency installation
- Added environment verification command

### 2. Backend Server Setup (tech.md)

**Enhanced API Deployment Commands:**
- **CRITICAL**: Added prominent instructions for starting FastAPI backend server
- Multiple start methods provided (uvicorn, direct Python, module execution)
- Added conda environment activation to all commands
- Comprehensive troubleshooting section for "Backend Offline" errors
- Port availability checking commands
- Import error debugging steps

### 3. Streamlit UI Integration (tech.md)

**Updated Streamlit Features:**
- Added requirement for FastAPI backend to be running for VCF patient profiles
- Clear instructions for running both Streamlit and FastAPI simultaneously
- Emphasized VCF Patient Profile Integration dependency

### 4. Product Overview Updates (product.md)

**Enhanced Core Functionality:**
- Added note about VCF Patient Profile Integration requiring FastAPI backend
- Updated Dual Interface Architecture description to highlight critical setup requirement

### 5. Project Structure Updates (structure.md)

**Enhanced Entry Points:**
- Updated `app.py` description to include VCF Patient Profile Integration requirements
- Added backend server dependency information

**Configuration Management:**
- Added conda environment management requirements
- Added backend server configuration notes

**Error Handling Patterns:**
- Added backend connectivity error handling
- Added environment validation guidance

### 6. Comprehensive Troubleshooting Section (tech.md)

**New Troubleshooting Guide:**
- **Backend Offline Error**: Step-by-step resolution for ReadTimeout errors
- **Import Errors**: Environment verification and dependency installation
- **Port Conflicts**: Port checking and alternative port usage
- **AWS Integration Issues**: Credential verification and service testing

## Impact

These updates address the critical user experience issue where:
1. Users were getting "Backend Offline" errors when using VCF patient profiles
2. The root cause was running in wrong conda environment (`base` instead of `synthatrial`)
3. FastAPI backend server wasn't running, preventing VCF functionality

## Files Updated

1. `.kiro/steering/tech.md` - Major updates to installation, API commands, troubleshooting
2. `.kiro/steering/product.md` - Added backend server requirements to core functionality
3. `.kiro/steering/structure.md` - Updated entry points and configuration management

## Next Steps

The steering documentation now provides:
- Clear environment setup requirements
- Comprehensive backend server startup instructions
- Detailed troubleshooting for common issues
- Proper conda environment management guidance

This ensures future users will have clear guidance to avoid the "Backend Offline" error and successfully use all platform features, especially VCF patient profile functionality.
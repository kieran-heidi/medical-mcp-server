# Medical Guidelines MCP Server

A production-ready Model Context Protocol (MCP) server that searches medical guidelines from authoritative sources and returns full-text content to Claude.ai for analysis.

## Features

- **Authoritative Sources**: Search NICE, RACGP, WHO, and CDC guidelines
- **No API Keys Required**: Uses DuckDuckGo HTML search for reliable results
- **Smart Content Extraction**: Site-specific parsing for optimal results
- **Rate Limiting**: Respectful crawling with built-in delays
- **Production Ready**: Railway deployment with health checks and monitoring
- **Claude.ai Compatible**: Full MCP over SSE protocol support

## Supported Medical Sources

- **NICE Guidelines** (nice.org.uk) - UK National Institute for Health and Care Excellence
- **RACGP Guidelines** (racgp.org.au) - Royal Australian College of General Practitioners
- **WHO Guidelines** (who.int) - World Health Organization
- **CDC Guidelines** (cdc.gov) - Centers for Disease Control and Prevention

## Quick Start

### 1. Fork/Clone the Repository

```bash
git clone https://github.com/yourusername/medical-mcp-server.git
cd medical-mcp-server
```

### 2. Deploy to Railway

1. **Connect to Railway**:
   - Go to [Railway.app](https://railway.app)
   - Sign in with your GitHub account
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your forked repository

2. **Deploy**:
   - Railway will automatically detect the Python application
   - The deployment will use the `Procfile` and `requirements.txt`
   - Wait for the build to complete (usually 2-3 minutes)

3. **Get Your URL**:
   - Once deployed, Railway will provide a public URL
   - Example: `https://your-app-name.railway.app`

### 3. Connect to Claude.ai

1. **Add MCP Server**:
   - Go to [Claude.ai](https://claude.ai)
   - Click on your profile → "Customize Claude"
   - Scroll to "Model Context Protocol (MCP)"
   - Click "Add MCP Server"

2. **Configure Connection**:
   - **Server URL**: `https://your-app-name.railway.app/sse`
   - **Server Name**: `Medical Guidelines MCP`
   - Click "Add Server"

3. **Test Connection**:
   - The server should connect successfully
   - You'll see "Medical Guidelines MCP" in your available tools

## Usage Examples

Once connected to Claude.ai, you can ask questions like:

### Basic Searches
- "Search NICE guidelines for diabetes management"
- "Find RACGP recommendations for hypertension treatment"
- "Get WHO guidelines on vaccination schedules"
- "Search CDC guidelines for mental health treatment"

### Specific Domain Searches
- "Search only NICE and WHO guidelines for cancer screening"
- "Find RACGP guidelines for pediatric care"

### Comparative Analysis
- "Compare NICE and CDC guidelines on COVID-19 prevention"
- "What are the differences between WHO and RACGP recommendations for diabetes?"

## API Response Format

The server returns formatted guideline content:

```
GUIDELINE: [Title]
SOURCE: [Domain Name] 
URL: [Full URL]
================================================================================

[Full extracted guideline text content]

================================================================================
END OF GUIDELINE
```

## Technical Details

### MCP Protocol Implementation

The server implements the MCP protocol over Server-Sent Events (SSE) with:

- **Tool Specification**: `search_medical_guidelines`
- **Input Schema**: Query, optional domains, max results (1-5)
- **Content Extraction**: Site-specific HTML parsing
- **Rate Limiting**: 1.5-second delays between requests

### Health Check Endpoint

Visit `/health` to check server status:

```json
{
  "status": "healthy",
  "uptime": "2:30:15",
  "timestamp": "2024-01-15T10:30:00Z",
  "supported_domains": ["nice.org.uk", "racgp.org.au", "who.int", "cdc.gov"],
  "mcp_protocol": "sse",
  "version": "1.0.0"
}
```

### Content Extraction Logic

- **NICE Guidelines**: Specialized parser for nice.org.uk structure
- **RACGP Guidelines**: Optimized for racgp.org.au layout
- **Generic Parser**: Fallback for WHO, CDC, and other medical sites
- **Text Cleaning**: Removes navigation, ads, and non-content elements
- **Length Limiting**: Truncates content to 8000 characters for readability

## Local Development

### Prerequisites

- Python 3.8+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/medical-mcp-server.git
cd medical-mcp-server

# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py
```

The server will start on `http://localhost:8080`

### Environment Variables

- `PORT`: Server port (default: 8080, Railway sets this automatically)

## Adding New Medical Sources

To add new medical domains, edit the `MEDICAL_DOMAINS` configuration in `main.py`:

```python
MEDICAL_DOMAINS = {
    'new-domain.org': {
        'name': 'New Medical Guidelines',
        'search_url': 'https://duckduckgo.com/html/?q=site:new-domain.org+{query}',
        'parser': 'generic'  # or 'nice', 'racgp' for specialized parsing
    },
    # ... existing domains
}
```

## Troubleshooting

### Common Issues

1. **Connection Failed**:
   - Check Railway deployment status
   - Verify the URL includes `/sse` endpoint
   - Ensure CORS headers are properly set

2. **No Results Found**:
   - Try different search terms
   - Check if the medical domain is supported
   - Verify the query is medical-related

3. **Content Extraction Issues**:
   - Some sites may block automated requests
   - Content structure may have changed
   - Check server logs for specific errors

### Railway Deployment Issues

1. **Build Failures**:
   - Check `requirements.txt` for correct dependencies
   - Verify `Procfile` syntax
   - Check Railway logs for specific errors

2. **Runtime Errors**:
   - Monitor Railway logs in the dashboard
   - Check health endpoint: `https://your-app.railway.app/health`
   - Verify environment variables are set correctly

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Check the troubleshooting section above
- Review Railway deployment logs
- Open an issue on GitHub

---

**Note**: This server respects rate limits and robots.txt guidelines. Please use responsibly and in accordance with the terms of service of the medical guideline websites. 
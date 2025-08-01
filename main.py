#!/usr/bin/env python3
"""
Medical Guidelines MCP Server
A production-ready MCP server for searching medical guidelines from authoritative sources.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus, urljoin, urlparse

import aiohttp
from aiohttp import web
from bs4 import BeautifulSoup
import aiohttp_cors

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Medical domains configuration
MEDICAL_DOMAINS = {
    'nice.org.uk': {
        'name': 'NICE Guidelines',
        'search_url': 'https://duckduckgo.com/html/?q=site:nice.org.uk+{query}',
        'parser': 'nice'
    },
    'racgp.org.au': {
        'name': 'RACGP Guidelines', 
        'search_url': 'https://duckduckgo.com/html/?q=site:racgp.org.au+{query}',
        'parser': 'racgp'
    },
    'who.int': {
        'name': 'WHO Guidelines',
        'search_url': 'https://duckduckgo.com/html/?q=site:who.int+{query}',
        'parser': 'generic'
    },
    'cdc.gov': {
        'name': 'CDC Guidelines',
        'search_url': 'https://duckduckgo.com/html/?q=site:cdc.gov+{query}',
        'parser': 'generic'
    }
}

class MedicalGuidelinesMCPServer:
    def __init__(self):
        self.app = web.Application()
        self.session = None
        self.start_time = datetime.now()
        self.setup_routes()
        self.setup_cors()
        
    def setup_routes(self):
        """Setup application routes"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/sse', self.sse_handler)
        self.app.router.add_post('/sse', self.sse_handler)
        
    def setup_cors(self):
        """Setup CORS for Claude.ai compatibility"""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
        
        # Add CORS to all routes
        for route in list(self.app.router.routes()):
            cors.add(route)
            
    async def start_session(self):
        """Initialize aiohttp session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            
    async def cleanup_session(self):
        """Cleanup aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
            
    async def health_check(self, request):
        """Health check endpoint for Railway"""
        uptime = datetime.now() - self.start_time
        health_data = {
            'status': 'healthy',
            'uptime': str(uptime),
            'timestamp': datetime.now().isoformat(),
            'supported_domains': list(MEDICAL_DOMAINS.keys()),
            'mcp_protocol': 'sse',
            'version': '1.0.0'
        }
        return web.json_response(health_data)
        
    async def sse_handler(self, request):
        """Handle MCP over SSE connections"""
        response = web.StreamResponse(
            status=200,
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': '*'
            }
        )
        
        await response.prepare(request)
        
        try:
            # Handle incoming messages
            async for line in request.content:
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        await self.handle_mcp_message(data, response)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON received: {line}")
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        
        except asyncio.CancelledError:
            logger.info("SSE connection cancelled")
        except Exception as e:
            logger.error(f"SSE handler error: {e}")
        finally:
            await self.cleanup_session()
            
    async def send_sse_message(self, response, data):
        """Send SSE message"""
        message = f"data: {json.dumps(data)}\n\n"
        await response.write(message.encode('utf-8'))
        
    async def handle_mcp_message(self, message, response):
        """Handle MCP protocol messages"""
        method = message.get('method')
        message_id = message.get('id')
        
        logger.info(f"Received MCP message: {method}")
        
        if method == 'tools/call':
            await self.handle_tool_call(message, response)
        elif method == 'initialize':
            await self.send_sse_message(response, {
                'jsonrpc': '2.0',
                'id': message_id,
                'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {
                        'tools': {
                            'listChanged': False
                        }
                    },
                    'serverInfo': {
                        'name': 'medical-guidelines-mcp',
                        'version': '1.0.0'
                    }
                }
            })
        elif method == 'tools/list':
            await self.send_sse_message(response, {
                'jsonrpc': '2.0',
                'id': message_id,
                'result': {
                    'tools': [{
                        'name': 'search_medical_guidelines',
                        'description': 'Search medical guidelines from authorized sources and return full text content',
                        'inputSchema': {
                            'type': 'object',
                            'properties': {
                                'query': {
                                    'type': 'string',
                                    'description': 'Search query for medical guidelines'
                                },
                                'domains': {
                                    'type': 'array',
                                    'items': {'type': 'string'},
                                    'description': 'Specific domains to search (optional)'
                                },
                                'max_results': {
                                    'type': 'integer',
                                    'default': 3,
                                    'minimum': 1,
                                    'maximum': 5
                                }
                            },
                            'required': ['query']
                        }
                    }]
                }
            })
        else:
            logger.warning(f"Unknown MCP method: {method}")
            
    async def handle_tool_call(self, message, response):
        """Handle tool call for medical guidelines search"""
        params = message.get('params', {})
        logger.info(f"Tool call params: {params}")
        
        # Handle different parameter formats that Claude might send
        query = params.get('query', '')
        
        # If query is the function name, try to get the actual query from arguments
        if query == 'search_medical_guidelines' or not query:
            # Look for the actual search query in the parameters
            if isinstance(params, dict):
                for key, value in params.items():
                    if (isinstance(value, str) and value.strip() and 
                        value.strip() != 'search_medical_guidelines' and
                        key != 'query'):
                        query = value.strip()
                        logger.info(f"Found query in parameter '{key}': '{query}'")
                        break
        
        domains = params.get('domains', [])
        max_results = params.get('max_results', 3)
        
        logger.info(f"Extracted query: '{query}', domains: {domains}, max_results: {max_results}")
        
        # If we still don't have a valid query, check if there are any string arguments
        if not query or query == 'search_medical_guidelines':
            # Try to extract from the full message
            full_message = str(message)
            logger.info(f"Full message for debugging: {full_message}")
            
            # Try to find any string that could be a search query
            search_terms = []
            if isinstance(params, dict):
                for key, value in params.items():
                    if isinstance(value, str) and value.strip() and value.strip() != 'search_medical_guidelines':
                        search_terms.append(value.strip())
            
            if search_terms:
                query = search_terms[0]
                logger.info(f"Using fallback query: '{query}'")
            else:
                await self.send_sse_message(response, {
                    'jsonrpc': '2.0',
                    'id': message.get('id'),
                    'error': {
                        'code': -32602,
                        'message': 'Query parameter is required. Please provide a search query like "diabetes management" or "hypertension guidelines".'
                    }
                })
                return
        
        # Preprocess the query to handle complex medical queries
        original_query = query
        query = self.preprocess_medical_query(query)
        logger.info(f"Original query: '{original_query}' -> Processed query: '{query}'")
        
        if not query:
            await self.send_sse_message(response, {
                'jsonrpc': '2.0',
                'id': message.get('id'),
                'error': {
                    'code': -32602,
                    'message': 'Could not extract medical condition from query. Try: "diabetes management", "hypertension guidelines", "fracture treatment".'
                }
            })
            return
            
        try:
            # Start the search
            await self.send_sse_message(response, {
                'jsonrpc': '2.0',
                'id': message.get('id'),
                'result': {
                    'content': [{
                        'type': 'text',
                        'text': f"Searching medical guidelines for: '{query}'..."
                    }]
                }
            })
            
            # Perform the search
            results = await self.search_medical_guidelines(query, domains, max_results)
            
            # Send results
            await self.send_sse_message(response, {
                'jsonrpc': '2.0',
                'id': message.get('id'),
                'result': {
                    'content': [{
                        'type': 'text',
                        'text': results
                    }]
                }
            })
            
        except Exception as e:
            logger.error(f"Error in tool call: {e}")
            await self.send_sse_message(response, {
                'jsonrpc': '2.0',
                'id': message.get('id'),
                'error': {
                    'code': -32603,
                    'message': f'Internal error: {str(e)}'
                }
            })
            
    async def search_medical_guidelines(self, query: str, domains: List[str], max_results: int) -> str:
        """Search medical guidelines and return formatted results"""
        await self.start_session()
        
        # Determine which domains to search
        search_domains = domains if domains else list(MEDICAL_DOMAINS.keys())
        valid_domains = [d for d in search_domains if d in MEDICAL_DOMAINS]
        
        if not valid_domains:
            return "No valid medical domains specified."
            
        all_results = []
        
        for domain in valid_domains[:max_results]:
            try:
                domain_config = MEDICAL_DOMAINS[domain]
                search_url = domain_config['search_url'].format(query=quote_plus(query))
                
                logger.info(f"Searching {domain} for: {query}")
                
                # Search for results
                search_results = await self.search_duckduckgo(search_url)
                
                # Extract content from each result
                for result in search_results[:2]:  # Limit to 2 results per domain
                    try:
                        content = await self.extract_guideline_content(result['url'], domain_config['parser'])
                        if content:
                            formatted_result = self.format_guideline_result(
                                result['title'], domain, result['url'], content
                            )
                            all_results.append(formatted_result)
                    except Exception as e:
                        logger.warning(f"Error extracting content from {result['url']}: {e}")
                        
                # Rate limiting
                await asyncio.sleep(1.5)
                
            except Exception as e:
                logger.error(f"Error searching {domain}: {e}")
                
        if not all_results:
            # Try a fallback search with broader terms
            logger.info(f"No results found, trying fallback search for: {query}")
            fallback_query = query.replace(" management", "").replace(" guidelines", "")
            fallback_results = await self.search_medical_guidelines(fallback_query, domains, max_results)
            if fallback_results and "No medical guidelines found" not in fallback_results:
                return fallback_results
            
            return f"No medical guidelines found for '{query}' in the specified domains. Try searching for specific conditions like 'diabetes', 'hypertension', or 'fracture'."
            
        return "\n\n".join(all_results)
        
    async def search_duckduckgo(self, search_url: str) -> List[Dict[str, str]]:
        """Search DuckDuckGo for medical guidelines"""
        try:
            logger.info(f"Searching DuckDuckGo: {search_url}")
            async with self.session.get(search_url) as response:
                if response.status != 200:
                    raise Exception(f"Search failed with status {response.status}")
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                results = []
                # Try different selectors for DuckDuckGo results
                selectors = ['.result__a', '.result__title', 'a[href^="http"]', '.result']
                
                for selector in selectors:
                    elements = soup.select(selector)
                    for element in elements:
                        href = element.get('href')
                        if href and href.startswith('http'):
                            title = element.get_text(strip=True)
                            if title and len(title) > 10:  # Filter out very short titles
                                results.append({
                                    'title': title,
                                    'url': href
                                })
                    
                    if results:  # If we found results, break
                        break
                
                logger.info(f"Found {len(results)} search results")
                return results[:5]  # Limit to 5 results
                
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []
            
    async def extract_guideline_content(self, url: str, parser_type: str) -> Optional[str]:
        """Extract content from medical guideline page"""
        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status != 200:
                    return None
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                if parser_type == 'nice':
                    return self.parse_nice_guideline(soup)
                elif parser_type == 'racgp':
                    return self.parse_racgp_guideline(soup)
                else:
                    return self.parse_generic_guideline(soup)
                    
        except Exception as e:
            logger.error(f"Content extraction error for {url}: {e}")
            return None
            
    def parse_nice_guideline(self, soup: BeautifulSoup) -> str:
        """Parse NICE guideline content"""
        # Remove navigation, ads, and non-content elements
        for element in soup.select('nav, .navigation, .breadcrumb, .advertisement, .sidebar, footer, header'):
            element.decompose()
            
        # Look for main content areas
        content_selectors = [
            '.content, .main-content, .guideline-content, .article-content',
            'main, article, .content-wrapper',
            '.body-content, .text-content'
        ]
        
        content = ""
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content = ' '.join([elem.get_text(separator=' ', strip=True) for elem in elements])
                break
                
        if not content:
            # Fallback to body text
            body = soup.find('body')
            if body:
                content = body.get_text(separator=' ', strip=True)
                
        return self.clean_text(content)
        
    def parse_racgp_guideline(self, soup: BeautifulSoup) -> str:
        """Parse RACGP guideline content"""
        # Remove navigation and non-content elements
        for element in soup.select('nav, .navigation, .breadcrumb, .advertisement, .sidebar, footer, header'):
            element.decompose()
            
        # Look for RACGP-specific content areas
        content_selectors = [
            '.content, .main-content, .guideline-content, .article-content',
            'main, article, .content-wrapper',
            '.body-content, .text-content, .guideline-body'
        ]
        
        content = ""
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content = ' '.join([elem.get_text(separator=' ', strip=True) for elem in elements])
                break
                
        if not content:
            # Fallback to body text
            body = soup.find('body')
            if body:
                content = body.get_text(separator=' ', strip=True)
                
        return self.clean_text(content)
        
    def parse_generic_guideline(self, soup: BeautifulSoup) -> str:
        """Parse generic medical guideline content"""
        # Remove navigation, ads, and non-content elements
        for element in soup.select('nav, .navigation, .breadcrumb, .advertisement, .sidebar, footer, header, .menu, .ads'):
            element.decompose()
            
        # Look for main content areas
        content_selectors = [
            '.content, .main-content, .article-content, .post-content',
            'main, article, .content-wrapper, .entry-content',
            '.body-content, .text-content, .content-body'
        ]
        
        content = ""
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content = ' '.join([elem.get_text(separator=' ', strip=True) for elem in elements])
                break
                
        if not content:
            # Fallback to body text
            body = soup.find('body')
            if body:
                content = body.get_text(separator=' ', strip=True)
                
        return self.clean_text(content)
        
    def clean_text(self, text: str) -> str:
        """Clean and format extracted text"""
        if not text:
            return ""
            
        # Remove extra whitespace and normalize
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = ' '.join(lines)
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Limit length to prevent overwhelming responses
        if len(text) > 8000:
            text = text[:8000] + "... [Content truncated for length]"
            
        return text
        
    def preprocess_medical_query(self, user_input: str) -> str:
        """Extract medical terms and format for guidelines search"""
        if not user_input:
            return ""
        
        # Convert to lowercase for processing
        text = user_input.lower().strip()
        
        # Remove common prefixes and modifiers
        prefixes_to_remove = [
            "nice", "guidelines", "management", "treatment", "recommendations",
            "search for", "find", "get", "show me", "look for"
        ]
        
        for prefix in prefixes_to_remove:
            text = text.replace(prefix, "").strip()
        
        # Extract medical conditions
        medical_conditions = self.extract_medical_conditions(text)
        
        if medical_conditions:
            # Use the first found condition with "management" suffix
            primary_condition = medical_conditions[0]
            return f"{primary_condition} management"
        
        # If no specific condition found, try to extract key medical terms
        medical_keywords = [
            "diabetes", "hypertension", "fracture", "pneumonia", "asthma", 
            "copd", "stroke", "heart", "cancer", "depression", "anxiety",
            "obesity", "arthritis", "osteoporosis", "dementia", "epilepsy"
        ]
        
        for keyword in medical_keywords:
            if keyword in text:
                return f"{keyword} management"
        
        return ""
    
    def extract_medical_conditions(self, text: str) -> List[str]:
        """Extract medical conditions from text"""
        # Common medical conditions and their variations
        medical_conditions = {
            "hip fracture": ["hip fracture", "fractured hip", "hip break"],
            "diabetes": ["diabetes", "diabetic", "type 1 diabetes", "type 2 diabetes"],
            "hypertension": ["hypertension", "high blood pressure", "htn"],
            "pneumonia": ["pneumonia", "lung infection"],
            "asthma": ["asthma", "asthmatic"],
            "copd": ["copd", "chronic obstructive pulmonary disease"],
            "stroke": ["stroke", "cerebrovascular accident", "cva"],
            "heart failure": ["heart failure", "cardiac failure", "chf"],
            "depression": ["depression", "major depressive disorder", "mdd"],
            "anxiety": ["anxiety", "anxiety disorder", "generalized anxiety"],
            "obesity": ["obesity", "overweight", "bmi"],
            "arthritis": ["arthritis", "rheumatoid arthritis", "osteoarthritis"],
            "osteoporosis": ["osteoporosis", "bone loss", "fragile bones"]
        }
        
        found_conditions = []
        
        for condition, variations in medical_conditions.items():
            for variation in variations:
                if variation in text:
                    found_conditions.append(condition)
                    break
        
        return found_conditions
    
    def format_guideline_result(self, title: str, domain: str, url: str, content: str) -> str:
        """Format guideline result for output"""
        domain_name = MEDICAL_DOMAINS[domain]['name']
        
        return f"""GUIDELINE: {title}
SOURCE: {domain_name} ({domain})
URL: {url}
================================================================================

{content}

================================================================================
END OF GUIDELINE"""

async def main():
    """Main application entry point"""
    port = int(os.environ.get('PORT', 8080))
    
    server = MedicalGuidelinesMCPServer()
    
    logger.info(f"Starting Medical Guidelines MCP Server on port {port}")
    logger.info(f"Health check available at: http://localhost:{port}/health")
    logger.info(f"SSE endpoint available at: http://localhost:{port}/sse")
    logger.info(f"Supported domains: {list(MEDICAL_DOMAINS.keys())}")
    
    try:
        runner = web.AppRunner(server.app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"Server started successfully on port {port}")
        
        # Keep the server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        await server.cleanup_session()
        if 'runner' in locals():
            await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main()) 
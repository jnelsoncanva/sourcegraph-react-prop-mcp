#!/usr/bin/env python3
"""
Sourcegraph MCP Server - Fixed version with proper protocol compliance

Features and functionality:
- Search code across Canva repositories using Sourcegraph CLI
- Find function/class definitions 
- Find references to symbols
- Search within specific repositories
- List available repositories
- Retrieve file contents from repositories using GraphQL API
- Build complex search queries with filters (language, file type, repository)
- Format results for Claude consumption
- Synchronous JSON-RPC protocol handling (MCP 2024-11-05 compliant)

File Content Retrieval Tool:
MCP Tool Name: get_file_content
Purpose: Retrieve the raw contents of a specific file from a Sourcegraph repository
API Method: GraphQL POST request to {src_endpoint}/.api/graphql
GraphQL Query Structure:
  query {
    repository(name: "REPO_NAME") {
      commit(rev: "REVISION") {
        blob(path: "FILE_PATH") {
          content
        }
      }
    }
  }
Parameters:
- repository_name (required): Full repository name (e.g., "github.com/Canva/canva")
- file_path (required): Path to the file within the repository (e.g., "src/main.js")
- revision (optional): Git commit hash, branch name, or tag (defaults to "HEAD")
- limit (optional): Maximum number of lines to return (1-10000, for partial reading)
- offset (optional): Line number to start from (0-based, for partial reading)
Authentication: Uses SRC_ACCESS_TOKEN in Authorization header as "token {token}"
Response: Returns the raw file content (full or partial) with syntax highlighting and metadata
Error Handling: GraphQL errors, HTTP errors, network timeouts, file not found, invalid offset
Partial Content: When limit/offset used, shows "lines X-Y of Z" and both partial/full file stats
"""

import sys
import json
import logging
import subprocess
import os
import datetime
import requests
from pathlib import Path
from typing import Dict, Any, List

# Immediate logging setup - write to dedicated log file as soon as possible
log_file = "/tmp/sourcegraph_mcp_server.log"
try:
    with open(log_file, "a") as f:
        f.write(f"\n=== Sourcegraph MCP Server started at {datetime.datetime.now()} ===\n")
        f.write(f"Python script path: {__file__}\n")
        f.write(f"Working directory: {os.getcwd()}\n")
        f.write(f"SRC_ENDPOINT: {os.getenv('SRC_ENDPOINT', 'NOT_SET')}\n")
        f.write(f"SRC_ACCESS_TOKEN: {os.getenv('SRC_ACCESS_TOKEN', 'NOT_SET')[:10]}...\n")
        f.write(f"sys.argv: {sys.argv}\n")
        f.flush()
except Exception as e:
    # If we can't write to the log file, at least try stderr
    print(f"[CRITICAL] Failed to write to log file {log_file}: {e}", file=sys.stderr)

# Configure logging to file (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/sourcegraph_mcp_server.log',
    filemode='a'
)
logger = logging.getLogger("sourcegraph-mcp")

class SourcegraphMCPServer:
    """MCP-compliant Sourcegraph code search server."""
    
    def __init__(self):
        self.running = True
        self.initialized = False
        self.client_capabilities = {}
        self.connection_tested = False
        
        # Log to dedicated file
        try:
            with open(log_file, "a") as f:
                f.write(f"SourcegraphMCPServer.__init__() called at {datetime.datetime.now()}\n")
                f.flush()
        except:
            pass
        
        # Setup Sourcegraph configuration
        self.src_endpoint = os.environ.get("SRC_ENDPOINT", "https://canva.sourcegraphcloud.com")
        
        self.src_access_token = self._get_access_token()
        
        # Debug: Log token info (first/last 4 chars only for security)
        if self.src_access_token:
            token_preview = f"{self.src_access_token[:4]}...{self.src_access_token[-4:]}" if len(self.src_access_token) > 8 else "too_short"
            logger.info(f"Initialized Sourcegraph MCP server with endpoint: {self.src_endpoint}")
            logger.info(f"Token preview: {token_preview} (length: {len(self.src_access_token)})")
        else:
            logger.error("No Sourcegraph access token found")
            sys.exit(1)
    
    def _get_access_token(self) -> str:
        """Get Sourcegraph access token from environment or file."""
        
        # Try environment variable first
        token = os.environ.get("SRC_ACCESS_TOKEN")
        if token and token.strip():
            return token.strip()
        
        # Try local token files
        token_files = [
            Path.home() / ".sourcegraph_token",
            Path.home() / ".sourcegraph_srccli_token"
        ]
        
        for token_file in token_files:
            if token_file.exists():
                try:
                    with open(token_file) as f:
                        token = f.read().strip()
                        if token and not token.startswith("[REDACTED"):
                            return token
                        logger.warning(f"Token file {token_file} appears to be redacted")
                except Exception as e:
                    logger.warning(f"Could not read token from {token_file}: {e}")
        
        logger.error("SRC_ACCESS_TOKEN not found in environment or token files")
        return ""
    
    def run(self):
        """Run the MCP server."""
        logger.info("Sourcegraph MCP server started. Waiting for input...")
        
        # Log to dedicated file
        try:
            with open(log_file, "a") as f:
                f.write(f"run() method called at {datetime.datetime.now()}\n")
                f.write(f"About to start main loop...\n")
                f.flush()
        except:
            pass
        
        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    logger.info("End of input stream, shutting down")
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                self.process_request(line)
                
            except KeyboardInterrupt:
                logger.info("Interrupted, shutting down")
                break
            except Exception as e:
                logger.error(f"Unhandled exception: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                break
        
        logger.info("Exiting main loop...")
        logger.info(f"Final state: running={self.running}, initialized={self.initialized}")
    
    def process_request(self, request_str: str):
        """Process a JSON-RPC request."""
        if not request_str:
            return
        
        try:
            request = json.loads(request_str)
            
            if isinstance(request, list):
                # Handle batch requests (for 2024-11-05 compatibility)
                responses = []
                for req in request:
                    response = self.handle_single_request(req)
                    if response:
                        responses.append(response)
                if responses:
                    self.send_response(responses)
                return
            
            response = self.handle_single_request(request)
            if response:
                self.send_response(response)
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {request_str}")
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
            self.send_response(response)
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def handle_single_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a single JSON-RPC request."""
        request_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})
        
        logger.info(f"Method call: {method}")
        
        try:
            result = self.handle_method(method, params)
            if request_id is not None and result is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
        except Exception as e:
            logger.error(f"Error handling method {method}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            if request_id is not None:
                error_code = -32000
                if "not found" in str(e).lower():
                    error_code = -32601
                elif "invalid" in str(e).lower() or "parameter" in str(e).lower():
                    error_code = -32602
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": error_code,
                        "message": str(e)
                    }
                }
        return None
    
    def send_response(self, response):
        """Send a JSON-RPC response."""
        try:
            response_str = json.dumps(response)
            
            # Log sent response to dedicated file
            try:
                with open(log_file, "a") as f:
                    f.write(f"Sending response at {datetime.datetime.now()}: {response_str}\n")
                    f.flush()
            except:
                pass
                
            print(response_str, flush=True)
        except Exception as e:
            logger.error(f"Error sending response: {str(e)}")
    
    def handle_method(self, method: str, params: Dict[str, Any]) -> Any:
        """Handle an MCP method call."""
        if method == "initialize":
            return self.handle_initialize(params)
        elif method == "initialized" or method == "notifications/initialized":
            # Handle the initialized notification that comes after initialize
            logger.info("Received initialized notification - ready for requests")
            return None
        elif method == "shutdown":
            self.running = False
            return {}
        elif method == "exit":
            self.running = False
            return None
        elif method == "tools/list":
            return self.handle_tools_list()
        elif method == "tools/call":
            return self.handle_tools_call(params)
        elif method == "server/info":
            return self.handle_server_info()
        elif method == "ping":
            return self.handle_ping()
        else:
            raise Exception(f"Method not found: {method}")
    
    def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the initialize method."""
        if "protocolVersion" not in params:
            raise Exception("Missing required parameter: protocolVersion")
        
        client_version = params.get("protocolVersion", "")
        self.client_capabilities = params.get("capabilities", {})
        client_info = params.get("clientInfo", {})
        
        if client_info:
            client_name = client_info.get("name", "Unknown")
            client_version_info = client_info.get("version", "Unknown")
            logger.info(f"Client: {client_name} {client_version_info}")
        
        logger.info(f"Client requested protocol version: {client_version}")
        
        # Support latest protocol versions
        supported_versions = ["2024-11-05", "2025-03-26", "2025-06-18"]
        
        if client_version not in supported_versions:
            raise Exception(f"This server supports protocol versions {supported_versions}. Requested: {client_version}")
        
        self.initialized = True
        self.protocol_version = client_version
        
        result = {
            "protocolVersion": client_version,
            "serverInfo": {
                "name": "Sourcegraph MCP Server",
                "version": "1.0.0"
            },
            "capabilities": {
                "tools": {
                    "listChanged": True
                }
            }
        }
        
        logger.info("Initialize successful")
        return result
    
    def handle_server_info(self) -> Dict[str, Any]:
        """Handle the server/info method."""
        return {
            "name": "Sourcegraph MCP Server",
            "version": "1.0.0",
            "supportedVersions": ["2024-11-05", "2025-03-26", "2025-06-18"]
        }
    
    def handle_ping(self) -> Dict[str, Any]:
        """Handle the ping method."""
        return {}
    
    def handle_tools_list(self) -> Dict[str, Any]:
        """Handle the tools/list method."""
        tools = [
            {
                "name": "search_code",
                "description": "Search the Canva codebase for code patterns, functions, or text. Can filter by repository, file type, and language. Use repository patterns like 'github.com/Canva/canva' for specific repos or '^github\\.com/Canva/' for all Canva repos.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (supports natural language or Sourcegraph syntax)"
                        },
                        "repository": {
                            "type": "string",
                            "description": "Optional repository pattern to limit search. Examples: 'github.com/Canva/canva' (specific repo), '^github\\.com/Canva/' (all Canva repos), 'infrastructure' (repos with 'infrastructure' in name), '^github\\.com/Canva/canva$' (exact match)",
                            "default": ""
                        },
                        "file_type": {
                            "type": "string",
                            "description": "Optional file type filter (e.g., '*.go', '*.ts', '*.py')",
                            "default": ""
                        },
                        "language": {
                            "type": "string",
                            "description": "Optional language filter (e.g., 'go', 'typescript', 'python')",
                            "default": ""
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "find_definition",
                "description": "Find the definition of a function, class, or symbol",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "The symbol to find (function name, class name, etc.)"
                        },
                        "language": {
                            "type": "string",
                            "description": "Optional language filter",
                            "default": ""
                        },
                        "repository": {
                            "type": "string",
                            "description": "Optional repository pattern. Examples: 'github.com/Canva/canva', '^github\\.com/Canva/', 'backend', '^github\\.com/Canva/canva$'",
                            "default": ""
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "find_references",
                "description": "Find all references/usages of a function, class, or symbol",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "The symbol to find references for"
                        },
                        "language": {
                            "type": "string",
                            "description": "Optional language filter",
                            "default": ""
                        },
                        "repository": {
                            "type": "string",
                            "description": "Optional repository pattern. Examples: 'github.com/Canva/canva', '^github\\.com/Canva/', 'backend', '^github\\.com/Canva/canva$'",
                            "default": ""
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "search_in_repository",
                "description": "Search within a specific repository. Use this when you want to focus on a particular repo like 'github.com/Canva/canva' (main app) or 'github.com/Canva/infrastructure' (infra).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repository": {
                            "type": "string",
                            "description": "Repository name or pattern. Examples: 'github.com/Canva/canva' (main app), 'github.com/Canva/infrastructure' (infra), '^github\\.com/Canva/' (all Canva repos), 'backend' (repos with 'backend' in name)"
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 15,
                            "minimum": 1,
                            "maximum": 50
                        }
                    },
                    "required": ["repository", "query"]
                }
            },
            {
                "name": "list_repositories",
                "description": "Discover available repositories in the Canva organization. Useful for finding specific repositories before searching.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Optional pattern to filter repository names (e.g., 'backend', 'infrastructure', 'api')",
                            "default": ""
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of repositories to return",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 50
                        }
                    }
                }
            },
            {
                "name": "get_file_content",
                "description": "Retrieve the raw contents of a specific file from a Sourcegraph repository. Useful for reading configuration files, source code, documentation, etc.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "repository_name": {
                            "type": "string",
                            "description": "Full repository name (e.g., 'github.com/Canva/canva', 'github.com/Canva/infrastructure')"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file within the repository (e.g., 'src/main.js', 'README.md', 'config/settings.yml')"
                        },
                        "revision": {
                            "type": "string",
                            "description": "Optional git commit hash, branch name, or tag (defaults to 'HEAD' for default branch)",
                            "default": "HEAD"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Optional maximum number of lines to return (for partial file reading)",
                            "minimum": 1,
                            "maximum": 10000
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Optional line number to start from (0-based, for partial file reading)",
                            "minimum": 0
                        }
                    },
                    "required": ["repository_name", "file_path"]
                }
            }
        ]
        return {"tools": tools}
    
    def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the tools/call method."""
        if "name" not in params:
            raise Exception("Missing required parameter: name")
        if "arguments" not in params:
            raise Exception("Missing required parameter: arguments")
        
        tool_name = params["name"]
        arguments = params["arguments"]
        

        try:
            # Strict parameter validation BEFORE connection test
            if tool_name == "search_code":
                # Check if arguments is empty or doesn't have the required parameters
                if not arguments or "query" not in arguments or not arguments.get("query") or (isinstance(arguments.get("query"), str) and not arguments["query"].strip()):
                    raise Exception("Missing or empty required parameter: query")
            elif tool_name == "find_definition":
                if not arguments or "symbol" not in arguments or not arguments.get("symbol") or (isinstance(arguments.get("symbol"), str) and not arguments["symbol"].strip()):
                    raise Exception("Missing or empty required parameter: symbol")
            elif tool_name == "find_references":
                if not arguments or "symbol" not in arguments or not arguments.get("symbol") or (isinstance(arguments.get("symbol"), str) and not arguments["symbol"].strip()):
                    raise Exception("Missing or empty required parameter: symbol")
            elif tool_name == "search_in_repository":
                if not arguments or "repository" not in arguments or not arguments.get("repository") or (isinstance(arguments.get("repository"), str) and not arguments["repository"].strip()):
                    raise Exception("Missing or empty required parameter: repository")
                if not arguments or "query" not in arguments or not arguments.get("query") or (isinstance(arguments.get("query"), str) and not arguments["query"].strip()):
                    raise Exception("Missing or empty required parameter: query")
            elif tool_name == "get_file_content":
                if not arguments or "repository_name" not in arguments or not arguments.get("repository_name") or (isinstance(arguments.get("repository_name"), str) and not arguments["repository_name"].strip()):
                    raise Exception("Missing or empty required parameter: repository_name")
                if not arguments or "file_path" not in arguments or not arguments.get("file_path") or (isinstance(arguments.get("file_path"), str) and not arguments["file_path"].strip()):
                    raise Exception("Missing or empty required parameter: file_path")
            elif tool_name not in ["list_repositories"]:
                raise Exception(f"Unknown tool: {tool_name}")
            
            # Test connection on first tool call (after parameter validation)
            if not self.connection_tested:
                try:
                    self._execute_src_command(["search", "-less=false", "context:global count:1 test"])
                    logger.info("✅ Sourcegraph connection test successful")
                    self.connection_tested = True
                except Exception as e:
                    logger.error(f"❌ Sourcegraph connection test failed: {e}")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error: Sourcegraph connection failed: {str(e)}\n\nPlease ensure SRC_ENDPOINT and SRC_ACCESS_TOKEN are configured correctly."
                            }
                        ]
                    }
            
            # Execute the tool
            if tool_name == "search_code":
                result = self.search_code(**arguments)
            elif tool_name == "find_definition":
                result = self.find_definition(**arguments)
            elif tool_name == "find_references":
                result = self.find_references(**arguments)
            elif tool_name == "search_in_repository":
                result = self.search_in_repository(**arguments)
            elif tool_name == "list_repositories":
                result = self.list_repositories(**arguments)
            elif tool_name == "get_file_content":
                result = self.get_file_content(**arguments)
            else:
                raise Exception(f"Unknown tool: {tool_name}")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": result
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Error in tool call {tool_name}: {e}")
            # Return proper JSON-RPC error response instead of content
            raise e
    
    def search_code(
        self, 
        query: str, 
        repository: str = "", 
        file_type: str = "", 
        language: str = "", 
        max_results: int = 10
    ) -> str:
        """Search for code using Sourcegraph."""
        search_query = self._build_search_query(
            base_query=query,
            repository=repository,
            file_type=file_type,
            language=language,
            max_results=max_results
        )
        result = self._execute_src_command(["search", "-less=false", search_query])
        return self._format_search_results(result, query)
    
    def find_definition(
        self, 
        symbol: str, 
        language: str = "", 
        repository: str = ""
    ) -> str:
        """Find the definition of a symbol."""
        definition_terms = ["def", "function", "class", "interface", "type"]
        search_terms = " OR ".join(f"{term} {symbol}" for term in definition_terms)
        
        search_query = self._build_search_query(
            base_query=f"({search_terms}) {symbol}",
            repository=repository,
            language=language,
            max_results=10
        )
        
        result = self._execute_src_command(["search", "-less=false", search_query])
        return self._format_search_results(result, f"definition of {symbol}")
    
    def find_references(
        self, 
        symbol: str, 
        language: str = "", 
        repository: str = "", 
        max_results: int = 20
    ) -> str:
        """Find references to a symbol."""
        search_query = self._build_search_query(
            base_query=symbol,
            repository=repository,
            language=language,
            max_results=max_results
        )
        
        result = self._execute_src_command(["search", "-less=false", search_query])
        return self._format_search_results(result, f"references to {symbol}")
    
    def search_in_repository(
        self, 
        repository: str, 
        query: str, 
        max_results: int = 15
    ) -> str:
        """Search within a specific repository."""
        search_query = self._build_search_query(
            base_query=query,
            repository=repository,
            max_results=max_results
        )
        
        result = self._execute_src_command(["search", "-less=false", search_query])
        return self._format_search_results(result, f"'{query}' in {repository}")
    
    def list_repositories(
        self, 
        pattern: str = "",
        max_results: int = 20
    ) -> str:
        """List available repositories."""
        
        if pattern:
            search_query = f"context:global count:{max_results} repo:{pattern} type:file file:README"
        else:
            search_query = f"context:global count:{max_results} repo:^github\\.com/Canva/ type:file file:README"
        
        try:
            result = self._execute_src_command(["search", "-less=false", search_query])
            
            repositories = set()
            lines = result.split('\n')
            
            for line in lines:
                if 'github.com/Canva/' in line and '›' in line:
                    parts = line.split('github.com/Canva/')
                    if len(parts) > 1:
                        repo_part = parts[1].split('›')[0].strip()
                        if repo_part:
                            repositories.add(f"github.com/Canva/{repo_part}")
            
            if repositories:
                repo_list = sorted(list(repositories))
                formatted = f"## Available Canva Repositories\n\n"
                formatted += f"**Found {len(repo_list)} repositories"
                if pattern:
                    formatted += f" matching '{pattern}'"
                formatted += ":**\n\n"
                
                for repo in repo_list:
                    formatted += f"- `{repo}`\n"
                
                formatted += f"\n**Usage Examples:**\n"
                formatted += f"- Search in main app: `repository: github.com/Canva/canva`\n"
                formatted += f"- Search all Canva repos: `repository: ^github\\.com/Canva/`\n"
                formatted += f"- Search by name pattern: `repository: infrastructure`\n"
                
            else:
                formatted = f"No repositories found"
                if pattern:
                    formatted += f" matching pattern '{pattern}'"
                formatted += ". Try a broader pattern or check your access permissions."
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error listing repositories: {e}")
            return f"Error listing repositories: {str(e)}\n\nCommon repository patterns:\n- github.com/Canva/canva (main application)\n- github.com/Canva/infrastructure (infrastructure)\n- ^github\\.com/Canva/ (all Canva repositories)"

    def get_file_content(
        self,
        repository_name: str,
        file_path: str,
        revision: str = "HEAD",
        limit: int = None,
        offset: int = None
    ) -> str:
        """Retrieve file contents using Sourcegraph GraphQL API."""
        
        # GraphQL query to get file content
        graphql_query = {
            "query": """
                query($repoName: String!, $revision: String!, $filePath: String!) {
                    repository(name: $repoName) {
                        commit(rev: $revision) {
                            blob(path: $filePath) {
                                content
                            }
                        }
                    }
                }
            """,
            "variables": {
                "repoName": repository_name,
                "revision": revision,
                "filePath": file_path
            }
        }
        
        # Prepare headers
        headers = {
            "Authorization": f"token {self.src_access_token}",
            "Content-Type": "application/json"
        }
        
        # Construct GraphQL endpoint URL
        graphql_url = f"{self.src_endpoint}/.api/graphql"
        
        try:
            logger.info(f"Fetching file content: {repository_name}:{revision}:{file_path}")
            
            response = requests.post(
                graphql_url,
                headers=headers,
                json=graphql_query,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"GraphQL request failed: {error_msg}")
                raise Exception(f"GraphQL request failed: {error_msg}")
            
            result = response.json()
            
            # Check for GraphQL errors
            if "errors" in result:
                error_details = result["errors"][0].get("message", "Unknown GraphQL error")
                logger.error(f"GraphQL error: {error_details}")
                raise Exception(f"GraphQL error: {error_details}")
            
            # Extract file content from response
            data = result.get("data", {})
            repository = data.get("repository")
            
            if not repository:
                raise Exception(f"Repository '{repository_name}' not found or not accessible")
            
            commit = repository.get("commit")
            if not commit:
                raise Exception(f"Revision '{revision}' not found in repository '{repository_name}'")
            
            blob = commit.get("blob")
            if not blob:
                raise Exception(f"File '{file_path}' not found at revision '{revision}' in repository '{repository_name}'")
            
            content = blob.get("content")
            if content is None:
                raise Exception(f"Could not retrieve content for file '{file_path}'")
            
            # Handle partial content if limit/offset specified
            original_lines = content.split('\n')
            total_lines = len(original_lines)
            
            if offset is not None or limit is not None:
                start_line = offset if offset is not None else 0
                if start_line >= total_lines:
                    raise Exception(f"Offset {start_line} exceeds file length ({total_lines} lines)")
                
                if limit is not None:
                    end_line = start_line + limit
                    selected_lines = original_lines[start_line:end_line]
                else:
                    selected_lines = original_lines[start_line:]
                
                content = '\n'.join(selected_lines)
                
                # Format the response for partial content
                actual_end = min(start_line + len(selected_lines), total_lines)
                formatted_response = f"## File Content: {repository_name}:{revision}:{file_path} (lines {start_line + 1}-{actual_end} of {total_lines})\n\n"
            else:
                # Format the response for full content
                formatted_response = f"## File Content: {repository_name}:{revision}:{file_path}\n\n"
            
            # Detect file type and add appropriate syntax highlighting
            file_extension = file_path.split('.')[-1].lower() if '.' in file_path else 'text'
            
            # Map common extensions to language identifiers for syntax highlighting
            extension_map = {
                'js': 'javascript',
                'ts': 'typescript',
                'jsx': 'jsx',
                'tsx': 'tsx',
                'py': 'python',
                'go': 'go',
                'java': 'java',
                'cpp': 'cpp',
                'c': 'c',
                'h': 'c',
                'hpp': 'cpp',
                'css': 'css',
                'html': 'html',
                'xml': 'xml',
                'json': 'json',
                'yaml': 'yaml',
                'yml': 'yaml',
                'md': 'markdown',
                'sh': 'bash',
                'sql': 'sql',
                'dockerfile': 'dockerfile'
            }
            
            language = extension_map.get(file_extension, 'text')
            
            formatted_response += f"```{language}\n{content}\n```\n"
            
            # Add file metadata
            lines_count = len(content.split('\n'))
            chars_count = len(content)
            
            if offset is not None or limit is not None:
                formatted_response += f"\n**Partial File Info:** {lines_count} lines shown, {chars_count} characters"
                formatted_response += f"\n**Full File Info:** {total_lines} total lines in file"
            else:
                formatted_response += f"\n**File Info:** {lines_count} lines, {chars_count} characters"
            
            return formatted_response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error retrieving file content: {e}")
            return f"Network error: {str(e)}\n\nPlease check your connection and Sourcegraph endpoint configuration."
        except Exception as e:
            logger.error(f"Error retrieving file content: {e}")
            return f"Error retrieving file '{file_path}' from '{repository_name}' at revision '{revision}':\n{str(e)}"
    
    def _build_search_query(
        self, 
        base_query: str, 
        repository: str = "", 
        file_type: str = "", 
        language: str = "", 
        max_results: int = 10
    ) -> str:
        """Build a Sourcegraph search query with filters."""
        
        query_parts = []
        
        if "context:" not in base_query:
            query_parts.append("context:global")
        
        if "count:" not in base_query:
            query_parts.append(f"count:{max_results}")
        
        if repository:
            if repository.startswith("^") or repository.startswith("github.com"):
                query_parts.append(f"repo:{repository}")
            else:
                query_parts.append(f"repo:{repository}")
        
        if file_type:
            if not file_type.startswith("*."):
                file_type = f"*.{file_type}"
            query_parts.append(f"type:file path:{file_type}")
        
        if language:
            query_parts.append(f"lang:{language}")
        
        query_parts.append(base_query)
        
        return " ".join(query_parts)
    
    def _execute_src_command(self, args: List[str]) -> str:
        """Execute a src-cli command."""
        
        env = os.environ.copy()
        env["SRC_ENDPOINT"] = self.src_endpoint
        env["SRC_ACCESS_TOKEN"] = self.src_access_token
        
        cmd = ["src"] + args
        
        try:
            logger.info(f"Executing command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=30
            )
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Command failed"
                logger.error(f"src command failed: {error_msg}")
                raise Exception(f"Sourcegraph search failed: {error_msg}")
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            raise Exception("Search timed out")
        except Exception as e:
            logger.error(f"Error executing src command: {e}")
            raise Exception(f"Failed to execute search: {str(e)}")
    
    def _format_search_results(self, raw_output: str, query_description: str) -> str:
        """Format Sourcegraph search results for Claude."""
        
        if not raw_output.strip():
            return f"No results found for: {query_description}"
        
        lines = raw_output.strip().split('\n')
        result_count = "Unknown"
        timing = ""
        
        for line in lines[:3]:
            if "results for" in line and "in" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.startswith('✱') and i + 1 < len(parts):
                        result_count = parts[i + 1]
                    elif part.endswith('ms') or part.endswith('s'):
                        timing = f" ({part})"
                break
        
        formatted = f"## Search Results for: {query_description}\n\n"
        formatted += f"**Found:** {result_count}{timing}\n\n"
        
        formatted += "```\n"
        formatted += raw_output
        formatted += "\n```\n"
        
        formatted += "\n**Note:** Results show file paths, line numbers, and code snippets. "
        formatted += "Click on the URLs to view files in Sourcegraph's web interface."
        
        return formatted

def main():
    """Main entry point."""
    # Log to dedicated file
    try:
        with open(log_file, "a") as f:
            f.write(f"main() function called at {datetime.datetime.now()}\n")
            f.write(f"About to create SourcegraphMCPServer...\n")
            f.flush()
    except:
        pass
    
    server = SourcegraphMCPServer()
    
    try:
        with open(log_file, "a") as f:
            f.write(f"SourcegraphMCPServer created, about to call run()...\n")
            f.flush()
    except:
        pass
    
    server.run()
    
    logger.info("Server.run() completed, main() exiting")

if __name__ == "__main__":
    main()

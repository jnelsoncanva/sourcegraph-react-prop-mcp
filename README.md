# Sourcegraph MCP Server

A Model Context Protocol (MCP) server that enables Claude Desktop to search the Canva codebase using natural language queries through Sourcegraph.

## Overview

This MCP server bridges Claude Desktop and Sourcegraph, allowing developers to:
- Search code using natural language queries
- Find function and class definitions
- Locate symbol references across the codebase
- Explore specific repositories
- Get contextual code information without leaving Claude conversations

## Features

### 🔍 **Six Powerful Search Tools**

#### `search_code`
General code search with advanced filtering capabilities.
```
Parameters:
- query: Natural language or Sourcegraph syntax
- repository: Optional repository pattern filter
- file_type: Optional file extension filter (*.go, *.ts, etc.)
- language: Optional language filter (go, typescript, python, etc.)
- max_results: Result limit (1-50, default: 10)
```

#### `find_definition`
Locate function, class, or symbol definitions.
```
Parameters:
- symbol: The symbol to find (function name, class name, etc.)
- language: Optional language filter
- repository: Optional repository pattern
```

#### `find_references`
Find all usages of a symbol across the codebase.
```
Parameters:
- symbol: The symbol to find references for
- language: Optional language filter
- repository: Optional repository pattern
- max_results: Result limit (1-100, default: 20)
```

#### `search_in_repository`
Search within a specific repository.
```
Parameters:
- repository: Repository name or pattern
- query: Search query
- max_results: Result limit (1-50, default: 15)
```

#### `list_repositories`
Discover available repositories in the Canva organization.
```
Parameters:
- pattern: Optional pattern to filter repository names
- max_results: Result limit (1-50, default: 20)
```

#### `get_file_content`
Retrieve raw file contents from Sourcegraph repositories.
```
Parameters:
- repository_name: Full repository name (e.g., 'github.com/Canva/canva')
- file_path: Path to file (e.g., 'src/main.js', 'README.md')
- revision: Optional git commit/branch/tag (defaults to 'HEAD')
- limit: Optional max lines to return (1-10,000) for partial reading
- offset: Optional starting line number (0-based) for partial reading
```

### 🎯 **Intelligent Query Processing**
- **Natural Language**: Converts plain English to Sourcegraph syntax
- **Auto-Enhancement**: Adds context and result limits automatically
- **Filter Combination**: Seamlessly combines multiple search filters
- **Error Recovery**: Graceful handling of query syntax issues

### 🔐 **Secure Authentication**
- **Token-Based**: Uses Sourcegraph personal access tokens
- **Environment Variables**: Secure credential management
- **Connection Validation**: Tests authentication before starting
- **Permission Inheritance**: Respects user's Sourcegraph permissions

### 🚀 **Advanced File Access**
- **GraphQL Integration**: Direct API access to Sourcegraph's file system
- **Partial Content Support**: Read specific sections of large files
- **Syntax Highlighting**: Automatic language detection and formatting
- **Revision Support**: Access files from any commit, branch, or tag
- **Efficient Streaming**: Handle large files with pagination support

## Quick Start

### Prerequisites
- Python 3.8+
- src-cli (Sourcegraph CLI) installed
- Valid Sourcegraph access token for canva.sourcegraphcloud.com
- Claude Desktop installed

### Installation

1. **Clone or download this repository**

2. **Create Sourcegraph access token:**
   - Visit: https://canva.sourcegraphcloud.com/user/settings/tokens
   - Create a new token
   - Save to: `~/.sourcegraph_token`

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Test the server:**
   ```bash
   ./run.sh
   ```

5. **Configure Claude Desktop:**
   Add to `~/.config/claude-desktop/config.json`:
   ```json
   {
     "mcpServers": {
       "sourcegraph": {
         "command": "/path/to/sourcegraph-mcp-server/run.sh"
       }
     }
   }
   ```

6. **Restart Claude Desktop** and test by asking:
   - "Search the codebase for authentication functions"
   - "Find the definition of validateUser"  
   - "Show me the contents of README.md"

## Repository Pattern Guide

### Common Repository Patterns

#### **Exact Repository Match**
```
"github.com/Canva/canva"           # Main Canva application
"github.com/Canva/infrastructure"  # Infrastructure repository
```

#### **Organization-wide Search**
```
"^github\.com/Canva/"             # All Canva repositories (regex)
```

#### **Pattern Matching**
```
"backend"                         # Any repo with "backend" in name
"infrastructure"                  # Any repo with "infrastructure" in name
"api"                            # Any repo with "api" in name
```

#### **Regex Patterns**
```
"^github\.com/Canva/canva$"       # Exact match only
"^github\.com/Canva/(canva|infrastructure)" # Multiple specific repos
"^github\.com/canvanauts/"        # All canvanauts repos
```

### Repository Discovery

Use the `list_repositories` tool to discover available repositories:
> *"List all repositories"*
> *"Find repositories with 'backend' in the name"*
> *"Show me infrastructure-related repositories"*

## Usage Examples

### Repository-Specific Queries

**Main application search:**
> *"Search for authentication functions in the main Canva app"*
> *"Find JWT validation in github.com/Canva/canva"*

**Infrastructure search:**
> *"Find database connections in the infrastructure repository"*
> *"Search for Redis configuration in github.com/Canva/infrastructure"*

**Organization-wide search:**
> *"Find all authentication middleware across all Canva repositories"*
> *"Search for API rate limiting in any Canva repo"*

### Natural Language Queries

**Finding authentication code:**
> "Find all authentication middleware functions in the backend"

**JWT token handling:**
> "Show me how JWT tokens are validated in the codebase"

**API endpoint discovery:**
> "Find all endpoints that handle user data"

**Error handling patterns:**
> "How do we typically handle database connection errors?"

### Advanced Searches

**Repository-specific:**
> "Search for Redis connection code in the infrastructure repository"

**Language-specific:**
> "Find all TypeScript interfaces related to user authentication"

**File type filtering:**
> "Show me all Go files that contain database migration logic"

### File Content Retrieval

**Reading complete files:**
> "Show me the contents of the main README file"
> "Get the package.json from the main Canva repository"

**Reading specific file sections:**
> "Show me lines 100-150 of the main configuration file"
> "Get the first 50 lines of the server startup script"

**Examining files at specific revisions:**
> "Show me the authentication config from the v2.1.0 release"
> "Get the database schema from the staging branch"

## Configuration

### Environment Variables

- `SRC_ENDPOINT`: Sourcegraph instance URL (default: https://canva.sourcegraphcloud.com)
- `SRC_ACCESS_TOKEN`: Your Sourcegraph personal access token

### File Locations

- **Token Storage**: `~/.sourcegraph_token` (or `~/.sourcegraph_srccli_token`)
- **Claude Config**: `~/.config/claude-desktop/config.json`
- **Server Logs**: Written to stderr (visible in Claude Desktop logs)

## Troubleshooting

### Common Issues

#### "Authentication not configured"
- Ensure `~/.sourcegraph_token` exists and contains valid token
- Verify token has access to canva.sourcegraphcloud.com
- Token files should contain just the token string, no extra formatting

#### "Connection failed"
- Test src-cli directly: `src search 'context:global count:1 test'`
- Verify network connectivity to canva.sourcegraphcloud.com
- Check if token has expired

#### "MCP server not found"
- Verify Claude Desktop configuration file exists and points to correct path
- Check that `run.sh` has execute permissions (`chmod +x run.sh`)
- Ensure Python dependencies are installed (`pip install -r requirements.txt`)

#### "No results found"
- Try broader search terms
- Check repository access permissions
- Verify search syntax is correct

#### "Output appears truncated"
- The server automatically uses `-less=false` to disable paging
- If you see truncated results, it may be due to very large result sets
- Consider adding more specific filters to reduce result size

### Debug Mode

Enable detailed logging by setting log level in the server:
```python
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
```

### Testing the Server

Run the test suite to validate functionality:
```bash
cd /Users/jnelson/development/internal_automation/src/sourcegraph-mcp-server
source venv/bin/activate
source ../../../bin/sourcegraph_env.sh
python test_server.py
```

## Architecture

### Communication Flow
```
Claude Desktop → MCP Client → [STDIO/JSON-RPC] → MCP Server → Sourcegraph API
```

### Key Components

- **main.py**: Core MCP server implementation (650+ lines)
- **run.sh**: Server launcher with environment setup
- **requirements.txt**: Python dependencies (requests)
- **README.md**: This documentation

### Protocol Compliance

- **STDIO Communication**: Proper stdin/stdout JSON-RPC messaging
- **Error Handling**: All debug output routed to stderr
- **Stateless Design**: Each request is independent
- **Type Safety**: Full input validation and schema enforcement

## Security

### Token Management
- Tokens stored in environment variables or secure files
- Never logged or transmitted in plaintext
- Automatic token validation before use

### Access Control
- Inherits user's Sourcegraph permissions
- Repository access follows existing Sourcegraph rules
- No elevation of privileges

### Network Security
- Direct connection to Sourcegraph Cloud
- No data caching or persistence
- All communication over HTTPS

## Performance

### Response Times
- Simple searches: 2-5 seconds
- Complex queries: 5-10 seconds
- Connection test: <2 seconds

### Optimization
- Configurable result limits
- Intelligent query building
- Async command execution
- Minimal memory footprint

## Development

### Adding New Tools

1. **Define the tool schema** in `_register_handlers()`
2. **Implement the handler** method
3. **Add query building logic** in `_build_search_query()`
4. **Update tests** in `test_server.py`

### Code Structure

```
src/sourcegraph-mcp-server/
├── main.py              # Core MCP server
├── run_server.sh        # Production launcher
├── test_server.py       # Test suite
├── requirements.txt     # Dependencies
├── venv/               # Python virtual environment
└── README.md           # This file
```

## Support

### Getting Help

1. **Check the logs**: Claude Desktop console for MCP server output
2. **Test connectivity**: Run `test_server.py` to validate setup
3. **Verify configuration**: Ensure all files and tokens are correct
4. **Review documentation**: Check Sourcegraph and MCP documentation

### Known Limitations

- Maximum 100 results per query (Sourcegraph API limit)
- File content limited to 10,000 lines per request (use offset for larger files)
- English language queries work best
- Requires active internet connection

## Contributing

### Guidelines

1. **Follow Python best practices**
2. **Add tests for new functionality**
3. **Update documentation**
4. **Ensure MCP protocol compliance**

### Testing

Always test changes with:
```bash
python test_server.py
```

---

**Version**: 1.0.0  
**License**: MIT  
**Author**: Internal Automation Team  
**Last Updated**: June 13, 2025

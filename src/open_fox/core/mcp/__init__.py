"""MCP (Model Context Protocol) 客户端。

支持三种 transport：
- stdio：本地子进程 JSON-RPC
- sse：HTTP SSE 长连接
- streamable-http：HTTP streamable
"""
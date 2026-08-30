#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import axios from "axios";

class GrafanaMCPServer {
  private server: Server;
  private grafanaUrl: string;
  private serviceAccountToken: string;

  constructor() {
    this.server = new Server(
      {
        name: "grafana-mcp-server",
        version: "1.0.0",
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    // Get configuration from environment variables
    this.grafanaUrl = process.env.GRAFANA_URL || "http://localhost:3000";
    this.serviceAccountToken = process.env.GRAFANA_SERVICE_ACCOUNT_TOKEN || "";

    console.error(`🔧 Grafana MCP Server initialized:`);
    console.error(`   URL: ${this.grafanaUrl}`);
    console.error(`   Token present: ${!!this.serviceAccountToken}`);
    console.error(`   Token length: ${this.serviceAccountToken.length}`);

    this.setupToolHandlers();
    this.setupRequestHandlers();
  }

  private setupToolHandlers() {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: "search_dashboards",
            description: "Search for Grafana dashboards by query",
            inputSchema: {
              type: "object",
              properties: {
                query: {
                  type: "string",
                  description: "Search query for dashboards",
                },
                limit: {
                  type: "number",
                  description: "Maximum number of results to return",
                  default: 10,
                },
              },
              required: ["query"],
            },
          },
          {
            name: "get_dashboard_summary",
            description: "Get detailed information about a specific dashboard",
            inputSchema: {
              type: "object",
              properties: {
                uid: {
                  type: "string",
                  description: "Dashboard UID",
                },
              },
              required: ["uid"],
            },
          },
          {
            name: "query_prometheus",
            description: "Execute a Prometheus query",
            inputSchema: {
              type: "object",
              properties: {
                query: {
                  type: "string",
                  description: "PromQL query to execute",
                },
                datasource_uid: {
                  type: "string",
                  description: "Prometheus datasource UID (optional)",
                },
              },
              required: ["query"],
            },
          },
          {
            name: "query_loki",
            description: "Execute a Loki query for logs",
            inputSchema: {
              type: "object",
              properties: {
                query: {
                  type: "string",
                  description: "LogQL query to execute",
                },
                datasource_uid: {
                  type: "string",
                  description: "Loki datasource UID (optional)",
                },
              },
              required: ["query"],
            },
          },
          {
            name: "list_alert_rules",
            description: "List Grafana alert rules",
            inputSchema: {
              type: "object",
              properties: {},
            },
          },
          {
            name: "list_datasources",
            description: "List configured Grafana datasources",
            inputSchema: {
              type: "object",
              properties: {},
            },
          },
        ],
      };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case "search_dashboards":
            return await this.searchDashboards(args);
          case "get_dashboard_summary":
            return await this.getDashboardSummary(args);
          case "query_prometheus":
            return await this.queryPrometheus(args);
          case "query_loki":
            return await this.queryLoki(args);
          case "list_alert_rules":
            return await this.listAlertRules(args);
          case "list_datasources":
            return await this.listDatasources(args);
          default:
            throw new McpError(
              ErrorCode.MethodNotFound,
              `Unknown tool: ${name}`
            );
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        throw new McpError(
          ErrorCode.InternalError,
          `Tool execution failed: ${errorMessage}`
        );
      }
    });
  }

  private setupRequestHandlers() {
    // Add any additional request handlers here if needed
  }

  private async makeGrafanaRequest(endpoint: string, method: string = "GET", params?: any) {
    const url = `${this.grafanaUrl}/api${endpoint}`;

    const headers = {
      "Authorization": `Bearer ${this.serviceAccountToken}`,
      "Content-Type": "application/json",
    };

    try {
      const response = await axios({
        method,
        url,
        headers,
        params,
        timeout: 10000, // 10 second timeout
      });

      return response.data;
    } catch (error: any) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      throw new Error(`Grafana API request failed: ${errorMessage}`);
    }
  }

  private async searchDashboards(args: any) {
    const { query = "", limit = 10 } = args;

    const data = await this.makeGrafanaRequest("/search", "GET", {
      query,
      limit,
      type: "dash-db",
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            dashboards: data.map((dashboard: any) => ({
              title: dashboard.title,
              uid: dashboard.uid,
              tags: dashboard.tags || [],
              url: dashboard.url,
            })),
            total: data.length,
          }),
        },
      ],
    };
  }

  private async getDashboardSummary(args: any) {
    const { uid } = args;

    const data = await this.makeGrafanaRequest(`/dashboards/uid/${uid}`);

    const dashboard = data.dashboard;
    const panels = dashboard.panels || [];

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            title: dashboard.title,
            uid: dashboard.uid,
            description: dashboard.description || "",
            panels: panels.map((panel: any) => ({
              title: panel.title,
              type: panel.type,
              datasource: panel.datasource?.type || "unknown",
            })),
            variables: dashboard.templating?.list?.map((v: any) => v.name) || [],
            tags: dashboard.tags || [],
          }),
        },
      ],
    };
  }

  private async queryPrometheus(args: any) {
    const { query, datasource_uid } = args;

    // Find Prometheus datasource if not specified
    let dsUid = datasource_uid;
    if (!dsUid) {
      const datasources = await this.makeGrafanaRequest("/datasources");
      const prometheusDs = datasources.find((ds: any) => ds.type === "prometheus");
      if (prometheusDs) {
        dsUid = prometheusDs.uid;
      }
    }

    if (!dsUid) {
      throw new Error("No Prometheus datasource found");
    }

    const data = await this.makeGrafanaRequest(`/datasources/proxy/uid/${dsUid}/api/v1/query`, "GET", {
      query,
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(data),
        },
      ],
    };
  }

  private async queryLoki(args: any) {
    const { query, datasource_uid } = args;

    // Find Loki datasource if not specified
    let dsUid = datasource_uid;
    if (!dsUid) {
      const datasources = await this.makeGrafanaRequest("/datasources");
      const lokiDs = datasources.find((ds: any) => ds.type === "loki");
      if (lokiDs) {
        dsUid = lokiDs.uid;
      }
    }

    if (!dsUid) {
      throw new Error("No Loki datasource found");
    }

    const data = await this.makeGrafanaRequest(`/datasources/proxy/uid/${dsUid}/loki/api/v1/query`, "GET", {
      query,
      limit: 100,
    });

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(data),
        },
      ],
    };
  }

  private async listAlertRules(args: any) {
    const data = await this.makeGrafanaRequest("/v1/provisioning/alert-rules");

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            rules: data.map((rule: any) => ({
              name: rule.title,
              state: rule.state || "unknown",
              labels: rule.labels || {},
              annotations: rule.annotations || {},
            })),
          }),
        },
      ],
    };
  }

  private async listDatasources(args: any) {
    const data = await this.makeGrafanaRequest("/datasources");

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            datasources: data.map((ds: any) => ({
              name: ds.name,
              type: ds.type,
              uid: ds.uid,
              url: ds.url,
              isDefault: ds.isDefault || false,
            })),
          }),
        },
      ],
    };
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("Grafana MCP server running on stdio");
  }
}

// Run the server
const server = new GrafanaMCPServer();
server.run().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
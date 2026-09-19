import { describe, expect, it } from "vitest";
import nginxConfig from "../../nginx.conf?raw";

describe("nginx OAuth proxy configuration", () => {
  it("preserves the public Host header including a non-default port", () => {
    expect(nginxConfig).toContain("proxy_set_header Host $http_host;");
    expect(nginxConfig).not.toMatch(/proxy_set_header Host \$host;/);
  });
});

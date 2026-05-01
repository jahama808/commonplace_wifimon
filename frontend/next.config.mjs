/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produce a self-contained `.next/standalone` build so the Docker image
  // can ship just the server.js + minimum node_modules.
  output: 'standalone',
  async rewrites() {
    const apiBase = process.env.API_BASE_URL || 'http://localhost:8000';
    return [
      { source: '/api/v1/:path*', destination: `${apiBase}/api/v1/:path*` },
    ];
  },
};

export default nextConfig;

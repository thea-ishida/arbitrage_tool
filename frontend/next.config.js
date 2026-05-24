/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Forward WebSocket traffic to the Python backend during development.
  // In production, replace with your actual backend host.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ];
  },
};

module.exports = nextConfig;

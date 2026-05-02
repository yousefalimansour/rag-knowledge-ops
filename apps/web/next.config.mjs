/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Hide the dev-mode "Static route / N" indicator that floats above the UI.
  devIndicators: {
    appIsrStatus: false,
    buildActivity: false,
  },
  // Same-origin proxy: browser hits /api/* → next forwards to FastAPI.
  // Lets us share cookies and dodge CORS pre-flight in the browser.
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://api:8000';
    return [
      { source: '/api/:path*', destination: `${apiUrl}/api/:path*` },
      { source: '/auth/:path*', destination: `${apiUrl}/auth/:path*` },
    ];
  },
};

export default nextConfig;

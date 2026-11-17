/** @type {import('next').NextConfig} */
const apiUrl = process.env.NEXT_PUBLIC_API_URL;

const nextConfig = {
  // Vercel manages the build output itself; standalone is only for the Docker image.
  ...(process.env.VERCEL ? {} : { output: 'standalone' }),
  async rewrites() {
    // On Vercel, /api/* is routed by the platform (same-origin function or a
    // separate backend project via NEXT_PUBLIC_API_URL). Everywhere else proxy
    // relative /api calls to the FastAPI service so there is no CORS or
    // localhost/127.0.0.1 mismatch.
    if (process.env.VERCEL) {
      return [];
    }
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl || 'http://localhost:8000'}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Optimización de transpilación y empaquetado para librerías visuales
  transpilePackages: ['lucide-react', 'lightweight-charts'],
  typescript: {
    // Garantiza que la compilación de producción falle si hay errores de tipos
    ignoreBuildErrors: false,
  },
  eslint: {
    // Evita que el bug de ESLint 9 (circular structure) bloquee el build en Vercel
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    const backendUrl = process.env.BACKEND_INTERNAL_URL || 'http://80.65.211.99:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

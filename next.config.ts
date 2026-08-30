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
    // Garantiza que la compilación de producción falle si hay errores de lint
    ignoreDuringBuilds: false,
  },
};

export default nextConfig;

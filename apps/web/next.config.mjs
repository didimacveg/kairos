/** @type {import('next').NextConfig} */
const coreUrl = process.env.KAIROS_CORE_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  // El navegador habla siempre con el mismo origen. Asi la cookie de sesion
  // puede ser SameSite=Strict y no hay CORS con credenciales en juego.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${coreUrl}/api/:path*` }];
  },
};

export default nextConfig;

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KAIROS",
  description: "Sistema personal local",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}

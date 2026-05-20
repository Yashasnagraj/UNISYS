import type { Metadata } from "next";
import { Geist, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "ResoScan — When can I walk again?",
  description:
    "Resonant Modal Spectroscopy. The AI answer to the question every fracture patient asks: when can I walk again? Built for UNISYS 2026.",
  metadataBase: new URL("https://resoscan.vercel.app"),
  openGraph: {
    title: "ResoScan — When can I walk again?",
    description:
      "A handheld diagnostic that listens to bone and predicts when a patient can bear weight again — without X-ray, without ₹25 lakh of equipment.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">{children}</body>
    </html>
  );
}

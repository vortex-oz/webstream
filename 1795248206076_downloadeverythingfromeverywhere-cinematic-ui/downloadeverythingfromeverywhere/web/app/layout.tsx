import type { Metadata, Viewport } from "next";
import "./globals.css";
import JsonLd from "./JsonLd";
import Pwa from "./Pwa";
import { HOME_TITLE, OG_IMAGE, SITE_DESC, SITE_KEYWORDS, SITE_NAME, SITE_URL, absUrl, websiteJsonLd } from "../lib/seo.js";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${HOME_TITLE} · ${SITE_NAME}`,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_DESC,
  applicationName: SITE_NAME,
  keywords: SITE_KEYWORDS,
  authors: [{ name: SITE_NAME, url: SITE_URL }],
  creator: SITE_NAME,
  publisher: SITE_NAME,
  category: "entertainment",
  referrer: "origin-when-cross-origin",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  icons: {
    icon: [
      { url: absUrl("/favicon.png"), type: "image/png", sizes: "1080x1080" },
      { url: absUrl("/icon-192.png"), type: "image/png", sizes: "192x192" },
      { url: absUrl("/icon-512.png"), type: "image/png", sizes: "512x512" },
    ],
    apple: [{ url: absUrl("/icon-192.png"), sizes: "192x192", type: "image/png" }],
    shortcut: absUrl("/favicon.png"),
  },
  manifest: "/manifest.json",
  openGraph: {
    title: `${HOME_TITLE} · ${SITE_NAME}`,
    description: SITE_DESC,
    url: SITE_URL,
    siteName: SITE_NAME,
    locale: "en_US",
    type: "website",
    images: [OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: `${HOME_TITLE} · ${SITE_NAME}`,
    description: SITE_DESC,
    images: [OG_IMAGE],
  },
  appleWebApp: {
    capable: true,
    title: SITE_NAME,
    statusBarStyle: "black-translucent",
  },
  formatDetection: { telephone: false, email: false, address: false },
};

export const revalidate = 3600;

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#121212",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="dns-prefetch" href="https://image.tmdb.org" />
        <link rel="preconnect" href="https://image.tmdb.org" />
        <link rel="dns-prefetch" href="https://api.themoviedb.org" />
        <link rel="preconnect" href="https://api.themoviedb.org" crossOrigin="anonymous" />
        <link rel="dns-prefetch" href="https://api.tenrai.org" />
        <link rel="preconnect" href="https://api.tenrai.org" crossOrigin="anonymous" />
        <link rel="dns-prefetch" href="https://cdn.myanimelist.net" />
        <link rel="preconnect" href="https://cdn.myanimelist.net" />
      </head>
      <body>
        <JsonLd data={websiteJsonLd()} />
        <Pwa />
        {children}
      </body>
    </html>
  );
}

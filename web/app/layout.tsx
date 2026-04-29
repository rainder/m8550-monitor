import type { Metadata, Viewport } from "next"
import { GeistSans } from "geist/font/sans"
import { GeistMono } from "geist/font/mono"

import "./globals.css"

export const metadata: Metadata = {
  title: "M8550 — Operations",
  description: "Live operational view of the TP-Link M8550 router",
  applicationName: "M8550",
  appleWebApp: {
    capable: true,
    title: "M8550",
    statusBarStyle: "black-translucent",
  },
}

export const viewport: Viewport = {
  themeColor: "#000000",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="bg-black text-zinc-50 min-h-screen antialiased font-sans">
        {children}
      </body>
    </html>
  )
}

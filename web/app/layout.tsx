import type { Metadata } from "next"
import { GeistSans } from "geist/font/sans"
import { GeistMono } from "geist/font/mono"

import "./globals.css"

export const metadata: Metadata = {
  title: "M8550 — Operations",
  description: "Live operational view of the TP-Link M8550 router",
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

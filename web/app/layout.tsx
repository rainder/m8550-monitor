import type { Metadata } from "next"

import "./globals.css"

export const metadata: Metadata = {
  title: "M8550 Monitor",
  description: "Live stats for the TP-Link M8550 router",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-zinc-950 text-zinc-100 min-h-screen">{children}</body>
    </html>
  )
}

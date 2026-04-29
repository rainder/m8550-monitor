import { ImageResponse } from "next/og"

export const size = { width: 180, height: 180 }
export const contentType = "image/png"

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#000",
          color: "#4ade80",
          fontSize: 112,
          fontWeight: 600,
          letterSpacing: -6,
          fontFamily:
            "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        }}
      >
        M
      </div>
    ),
    size,
  )
}

import { ImageResponse } from "next/og"

export const size = { width: 512, height: 512 }
export const contentType = "image/png"

export default function Icon() {
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
          fontSize: 320,
          fontWeight: 600,
          letterSpacing: -16,
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

export interface Sample {
  ts: number
  rxRate: number | null
  txRate: number | null
  online: boolean
  totalBytes: number | null
  // Signal — usually all 0 on this firmware (M8550 local CGI doesn't report).
  sigLevel: number | null
  rsrp: number | null
  rsrq: number | null
  snr: number | null
  ispName: string | null
  cpuPct: number | null         // 0..1
  memPct: number | null         // 0..1
  // Link config (these DO populate on M8550):
  connectedBand: string | null  // e.g. "B3;N40"
  endcStatus: number | null     // 1 = EN-DC active (5G NSA), 0 = LTE only
  networkType: number | null    // firmware-specific code (8 = 5G NSA)
  wanIpv4: string | null
  wanIpv6: string | null
}

export interface Client {
  mac: string
  name: string | null
  ip: string | null
  connType: "host_2g" | "host_5g" | "wired"
  bandwidth: number | null     // bytes/sec, combined RX+TX
  totalBytes: number | null    // cumulative
}

export interface CurrentResponse {
  sample: Sample | null
  clients: Client[]
  ageSeconds: number   // server time - sample.ts; 0 when no sample
}

export type HistoryRange = "1h" | "24h" | "7d"

export interface HistoryPoint {
  ts: number
  rxRate: number | null
  txRate: number | null
}

export interface HistoryResponse {
  range: HistoryRange
  points: HistoryPoint[]
}

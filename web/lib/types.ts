export interface Sample {
  ts: number
  rxRate: number | null
  txRate: number | null
  online: boolean
  totalBytes: number | null   // NEW (column existed in DB; now exposed)
  sigLevel: number | null     // NEW (0..5 bars)
  rsrp: number | null         // NEW (dBm, typically negative)
  rsrq: number | null         // NEW (dB, typically negative)
  snr: number | null          // NEW (dB)
  ispName: string | null      // NEW (e.g. "Bite")
  cpuPct: number | null       // NEW (0..1)
  memPct: number | null       // NEW (0..1)
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

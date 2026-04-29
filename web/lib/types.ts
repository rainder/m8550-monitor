export interface Sample {
  ts: number
  rxRate: number | null
  txRate: number | null
  online: boolean
  totalBytes: number | null
  sigLevel: number | null
  rsrp: number | null            // LTE serving-cell RSRP dBm
  rsrq: number | null            // LTE serving-cell RSRQ dB
  snr: number | null             // LTE serving-cell SNR ×10 (60 = 6.0 dB)
  ispName: string | null
  cpuPct: number | null         // 0..1
  memPct: number | null         // 0..1
  connectedBand: string | null  // e.g. "B3;N40"
  endcStatus: number | null     // 1 = EN-DC active (5G NSA), 0 = LTE only
  networkType: number | null    // firmware-specific code (8 = 5G NSA)
  wanIpv4: string | null
  wanIpv6: string | null
  // 5G NR primary cell
  ssRsrp: number | null          // dBm
  ssRsrq: number | null          // dB
  ssSinr: number | null          // ×10 (310 = 31.0 dB)
  nrSignalStrength: number | null  // 0..5
  nrBand: string | null
  // LTE primary cell extras
  lteSignalStrength: number | null
  lteBand: string | null
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

export type HistoryMode = "wan" | "clients"

export interface ClientSeries {
  mac: string
  name: string | null
  /** bandwidth at each tick, aligned to ClientHistoryResponse.ticks. null when no data */
  values: (number | null)[]
}

export interface ClientHistoryResponse {
  range: HistoryRange
  mode: "clients"
  ticks: number[]
  series: ClientSeries[]
}

/** Discriminated union — `mode` is the discriminator. */
export type HistoryResponseAny =
  | (HistoryResponse & { mode?: "wan" })
  | ClientHistoryResponse

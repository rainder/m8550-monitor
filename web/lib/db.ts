import Database from "better-sqlite3"

import type { Client, HistoryPoint, Sample } from "./types"

let db: Database.Database | null = null

function getDb(): Database.Database {
  if (db) return db
  const path = process.env.DB_PATH
  if (!path) throw new Error("DB_PATH not set")
  db = new Database(path, { readonly: true, fileMustExist: false })
  db.pragma("journal_mode = WAL")
  return db
}

interface SampleRow {
  ts: number
  rx_rate: number | null
  tx_rate: number | null
  online: number
  total_bytes: number | null
  sig_level: number | null
  rsrp: number | null
  rsrq: number | null
  snr: number | null
  isp_name: string | null
  cpu_pct: number | null
  mem_pct: number | null
}

export function latestSample(): Sample | null {
  const row = getDb()
    .prepare(
      "SELECT ts, rx_rate, tx_rate, online, " +
      "total_bytes, sig_level, rsrp, rsrq, snr, isp_name, cpu_pct, mem_pct " +
      "FROM samples ORDER BY ts DESC LIMIT 1",
    )
    .get() as SampleRow | undefined
  if (!row) return null
  return {
    ts: row.ts,
    rxRate: row.rx_rate,
    txRate: row.tx_rate,
    online: row.online === 1,
    totalBytes: row.total_bytes,
    sigLevel: row.sig_level,
    rsrp: row.rsrp,
    rsrq: row.rsrq,
    snr: row.snr,
    ispName: row.isp_name,
    cpuPct: row.cpu_pct,
    memPct: row.mem_pct,
  }
}

interface ClientRow {
  mac: string
  name: string | null
  ip: string | null
  conn_type: "host_2g" | "host_5g" | "wired"
  total_bytes: number | null
  bandwidth: number | null
}

export function clientsAt(ts: number): Client[] {
  const rows = getDb()
    .prepare(
      "SELECT mac, name, ip, conn_type, total_bytes, bandwidth FROM clients WHERE ts = ?",
    )
    .all(ts) as ClientRow[]
  return rows.map((r) => ({
    mac: r.mac,
    name: r.name,
    ip: r.ip,
    connType: r.conn_type,
    totalBytes: r.total_bytes,
    bandwidth: r.bandwidth,
  }))
}

interface HistoryRow {
  ts: number
  rx_rate: number | null
  tx_rate: number | null
}

export function samplesSince(sinceTs: number): HistoryPoint[] {
  const rows = getDb()
    .prepare(
      "SELECT ts, rx_rate, tx_rate FROM samples WHERE ts >= ? ORDER BY ts ASC",
    )
    .all(sinceTs) as HistoryRow[]
  return rows.map((r) => ({ ts: r.ts, rxRate: r.rx_rate, txRate: r.tx_rate }))
}

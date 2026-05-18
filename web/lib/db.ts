import Database from "better-sqlite3"

import type { Client, HistoryPoint, Sample, SmsMessage } from "./types"

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
  connected_band: string | null
  endc_status: number | null
  network_type: number | null
  wan_ipv4: string | null
  wan_ipv6: string | null
  ss_rsrp: number | null
  ss_rsrq: number | null
  ss_sinr: number | null
  nr_signal_strength: number | null
  nr_band: string | null
  lte_signal_strength: number | null
  lte_band: string | null
}

export function latestSample(): Sample | null {
  const row = getDb()
    .prepare(
      "SELECT ts, rx_rate, tx_rate, online, " +
      "total_bytes, sig_level, rsrp, rsrq, snr, isp_name, cpu_pct, mem_pct, " +
      "connected_band, endc_status, network_type, wan_ipv4, wan_ipv6, " +
      "ss_rsrp, ss_rsrq, ss_sinr, nr_signal_strength, nr_band, " +
      "lte_signal_strength, lte_band " +
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
    connectedBand: row.connected_band,
    endcStatus: row.endc_status,
    networkType: row.network_type,
    wanIpv4: row.wan_ipv4,
    wanIpv6: row.wan_ipv6,
    ssRsrp: row.ss_rsrp,
    ssRsrq: row.ss_rsrq,
    ssSinr: row.ss_sinr,
    nrSignalStrength: row.nr_signal_strength,
    nrBand: row.nr_band,
    lteSignalStrength: row.lte_signal_strength,
    lteBand: row.lte_band,
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

interface ClientHistoryRow {
  ts: number
  mac: string
  name: string | null
  bandwidth: number | null
}

export function clientHistorySince(sinceTs: number): ClientHistoryRow[] {
  return getDb()
    .prepare(
      "SELECT ts, mac, name, bandwidth FROM clients " +
      "WHERE ts >= ? ORDER BY ts ASC, mac ASC",
    )
    .all(sinceTs) as ClientHistoryRow[]
}

interface SmsRow {
  id: number
  sender: string
  content: string
  received_at: number
  unread: number
  synced_at: number
}

export function listSms(): { messages: SmsMessage[]; syncedAt: number } {
  // sms_messages didn't exist in older databases; tolerate that and report empty.
  const db = getDb()
  const exists = db
    .prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sms_messages'")
    .get()
  if (!exists) return { messages: [], syncedAt: 0 }

  const rows = db
    .prepare(
      "SELECT id, sender, content, received_at, unread, synced_at FROM sms_messages " +
      "ORDER BY received_at DESC, id DESC",
    )
    .all() as SmsRow[]
  const messages = rows.map((r) => ({
    id: r.id,
    sender: r.sender,
    content: r.content,
    receivedAt: r.received_at,
    unread: r.unread === 1,
  }))
  const syncedAt = rows.length ? rows[0].synced_at : 0
  return { messages, syncedAt }
}

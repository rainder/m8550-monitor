/**
 * Writable SQLite connection scoped to push_subscriptions only.
 * The main db.ts handle is read-only; this one exists because the web side
 * receives subscriptions from the browser and the collector reads them.
 */
import fs from "node:fs"

import Database from "better-sqlite3"

let writeDb: Database.Database | null = null

function getDb(): Database.Database {
  if (writeDb) return writeDb
  const path = process.env.DB_PATH
  if (!path) throw new Error("DB_PATH not set")
  writeDb = new Database(path, { readonly: false, fileMustExist: false })
  writeDb.pragma("journal_mode = WAL")
  writeDb.exec(
    "CREATE TABLE IF NOT EXISTS push_subscriptions (" +
    "  endpoint   TEXT PRIMARY KEY," +
    "  p256dh     TEXT NOT NULL," +
    "  auth       TEXT NOT NULL," +
    "  created_at INTEGER NOT NULL" +
    ")",
  )
  return writeDb
}

export function addSubscription(endpoint: string, p256dh: string, auth: string): void {
  getDb()
    .prepare(
      "INSERT OR REPLACE INTO push_subscriptions (endpoint, p256dh, auth, created_at) " +
      "VALUES (?, ?, ?, ?)",
    )
    .run(endpoint, p256dh, auth, Math.floor(Date.now() / 1000))
}

export function deleteSubscription(endpoint: string): void {
  getDb()
    .prepare("DELETE FROM push_subscriptions WHERE endpoint = ?")
    .run(endpoint)
}

export function readVapidPublicKey(): string | null {
  const path = process.env.VAPID_PATH || "/data/vapid.json"
  try {
    const raw = fs.readFileSync(path, "utf8")
    const parsed = JSON.parse(raw)
    return typeof parsed.public === "string" ? parsed.public : null
  } catch {
    return null
  }
}

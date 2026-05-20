/**
 * Writable handle for the user-action queues the web side feeds. The collector
 * drains them at the start of its tick. The main db.ts handle stays read-only
 * by design — only this module writes.
 */
import Database from "better-sqlite3"

let writeDb: Database.Database | null = null

function getDb(): Database.Database {
  if (writeDb) return writeDb
  const path = process.env.DB_PATH
  if (!path) throw new Error("DB_PATH not set")
  writeDb = new Database(path, { readonly: false, fileMustExist: false })
  writeDb.pragma("journal_mode = WAL")
  writeDb.exec(
    "CREATE TABLE IF NOT EXISTS sms_actions (" +
    "  id         INTEGER PRIMARY KEY AUTOINCREMENT," +
    "  sms_id     INTEGER NOT NULL," +
    "  action     TEXT NOT NULL," +
    "  created_at INTEGER NOT NULL" +
    ")",
  )
  writeDb.exec(
    "CREATE TABLE IF NOT EXISTS router_actions (" +
    "  id         INTEGER PRIMARY KEY AUTOINCREMENT," +
    "  action     TEXT NOT NULL," +
    "  created_at INTEGER NOT NULL" +
    ")",
  )
  return writeDb
}

export type SmsAction = "mark_read" | "delete"

export function enqueueSmsAction(smsId: number, action: SmsAction): void {
  getDb()
    .prepare("INSERT INTO sms_actions (sms_id, action, created_at) VALUES (?, ?, ?)")
    .run(smsId, action, Math.floor(Date.now() / 1000))
}

export type RouterAction = "reauth"

export function enqueueRouterAction(action: RouterAction): void {
  getDb()
    .prepare("INSERT INTO router_actions (action, created_at) VALUES (?, ?)")
    .run(action, Math.floor(Date.now() / 1000))
}

/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/utils/formatters.js

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

/**
 * Format bytes to human readable string
 * @param {number} bytes - The size in bytes
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted string (e.g. "1.5 MB")
 */
export function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i]
}

/**
 * Format bytes per second to human readable rate
 * @param {number} bytesPerSec - Bytes per second
 * @returns {string} Formatted string (e.g. "1.5 MB/s")
 */
export function formatRate(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec === 0) return '0 B/s'
  const k = 1024
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s']
  const i = Math.floor(Math.log(bytesPerSec) / Math.log(k))
  return parseFloat((bytesPerSec / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

/**
 * Format uptime seconds to readable string
 * @param {number} seconds - Total seconds
 * @returns {string} Formatted string (e.g. "2d 4h" or "4h 30m")
 */
export function formatUptime(seconds) {
  if (!seconds) return '0m'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

/**
 * Format date string to locale string
 * @param {string} dateStr - ISO date string
 * @returns {string} Localized date string
 */
export function formatDate(dateStr) {
  if (!dateStr) return 'N/A'
  return new Date(dateStr).toLocaleString()
}

/**
 * Format schedule time string (HH:MM) to AM/PM format
 * @param {string} time - Time string in HH:MM format
 * @returns {string} Formatted time (e.g. "2:30 PM")
 */
export function formatScheduleTime(time) {
  if (!time) return '00:00 AM'
  const [h, m] = time.split(':')
  const hour = parseInt(h, 10)
  const minute = m || '00'
  const period = hour >= 12 ? 'PM' : 'AM'
  const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour
  return `${displayHour}:${minute} ${period}`
}

/**
 * Format schedule object to AM/PM string
 * @param {Object} schedule - Schedule object with hour/minute properties
 * @returns {string} Formatted time (e.g. "2:30 PM")
 */
export function formatScheduleTimeFromSchedule(schedule) {
  if (!schedule) return 'Not configured'
  const hour = schedule.hour ?? 0
  const minute = schedule.minute ?? 0
  const period = hour >= 12 ? 'PM' : 'AM'
  const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour
  return `${displayHour}:${String(minute).padStart(2, '0')} ${period}`
}

/**
 * Get color class for progress bar based on percent
 * @param {number} percent - Percentage value (0-100)
 * @returns {string} Tailwind CSS color class
 */
export function getProgressColor(percent) {
  if (percent >= 90) return 'bg-red-500'
  if (percent >= 75) return 'bg-amber-500' // Using 75 to match SystemView logic, Dashboard used 70
  return 'bg-emerald-500'
}

/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/config/constants.js

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

export const POLLING = {
  BACKUP_OPERATIONS: 2000,
  DASHBOARD_METRICS: 30000,
}

export const TIMEOUTS = {
  DEFAULT: 30000,
  LONG_RUNNING: 300000, // 5 minutes
  MOUNT_BACKUP: 600000, // 10 minutes
}

export const PAGINATION = {
  PAGE_SIZE_OPTIONS: [10, 20, 50, 100],
  DEFAULT_PAGE_SIZE: 10,
}

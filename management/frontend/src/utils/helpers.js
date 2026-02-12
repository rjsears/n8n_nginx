/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
/management/frontend/src/utils/helpers.js

Part of the "n8n_nginx/n8n_management" suite
Version 3.0.0 - January 1st, 2026

Richard J. Sears
richard@n8nmanagement.net
https://github.com/rjsears
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

/**
 * Get icon component name for config file type
 * @param {Object} configFile - The config file object
 * @returns {string} Icon component name
 */
export function getConfigFileIcon(configFile) {
  if (configFile.is_ssl) return 'ShieldCheckIcon'
  if (configFile.name.endsWith('.env')) return 'KeyIcon'
  if (configFile.name.includes('nginx')) return 'ServerIcon'
  if (configFile.name.includes('docker')) return 'CubeIcon'
  return 'DocumentIcon'
}

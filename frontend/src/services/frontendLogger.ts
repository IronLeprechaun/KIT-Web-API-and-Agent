// KIT_Web/frontend/src/services/frontendLogger.ts

const MAX_LOG_ENTRIES = 500; // Max number of log entries to keep
const LOG_STORAGE_KEY = 'kit_frontend_logs';

interface LogEntry {
  timestamp: string;
  level: 'INFO' | 'ERROR' | 'WARN' | 'DEBUG';
  message: string;
  details?: any;
}

function getStoredLogs(): LogEntry[] {
  try {
    const storedLogs = localStorage.getItem(LOG_STORAGE_KEY);
    return storedLogs ? JSON.parse(storedLogs) : [];
  } catch (error) {
    console.error('[Logger] Error reading logs from localStorage:', error);
    return [];
  }
}

function saveLogs(logs: LogEntry[]): void {
  try {
    localStorage.setItem(LOG_STORAGE_KEY, JSON.stringify(logs));
  } catch (error) {
    console.error('[Logger] Error saving logs to localStorage:', error);
  }
}

function addLogEntry(level: LogEntry['level'], message: string, details?: any): void {
  const newEntry: LogEntry = {
    timestamp: new Date().toISOString(),
    level,
    message,
    details: details ? (typeof details === 'string' ? details : JSON.stringify(details, null, 2)) : undefined,
  };

  let logs = getStoredLogs();
  logs.push(newEntry);

  // Rotate logs if over limit
  if (logs.length > MAX_LOG_ENTRIES) {
    logs = logs.slice(logs.length - MAX_LOG_ENTRIES);
  }

  saveLogs(logs);

  // Also log to console for immediate visibility during development
  switch (level) {
    case 'INFO':
      console.info(`[FE_INFO] ${message}`, details || '');
      break;
    case 'ERROR':
      console.error(`[FE_ERROR] ${message}`, details || '');
      break;
    case 'WARN':
      console.warn(`[FE_WARN] ${message}`, details || '');
      break;
    case 'DEBUG':
      console.debug(`[FE_DEBUG] ${message}`, details || '');
      break;
    default:
      console.log(`[FE_LOG] ${message}`, details || '');
  }
}

export const FrontendLogger = {
  info: (message: string, details?: any) => addLogEntry('INFO', message, details),
  error: (message: string, details?: any) => addLogEntry('ERROR', message, details),
  warn: (message: string, details?: any) => addLogEntry('WARN', message, details),
  debug: (message: string, details?: any) => addLogEntry('DEBUG', message, details),
  getLogs: (): LogEntry[] => getStoredLogs(),
  clearLogs: (): void => {
    saveLogs([]);
    console.info('[Logger] Frontend logs cleared.');
  },
  downloadLogs: (): void => {
    const logs = getStoredLogs();
    const blob = new Blob([logs.map(log => `${log.timestamp} [${log.level}] ${log.message}${log.details ? '\nDetails: ' + log.details : ''}`).join('\n') ], { type: 'text/plain' });
    const anchor = document.createElement('a');
    anchor.href = URL.createObjectURL(blob);
    anchor.download = `kit_frontend_logs_${new Date().toISOString().split('T')[0]}.txt`;
    anchor.click();
    URL.revokeObjectURL(anchor.href);
    console.info('[Logger] Frontend logs download requested.');
  },
};

// Initial log to confirm logger is active
FrontendLogger.info('FrontendLogger initialized.'); 
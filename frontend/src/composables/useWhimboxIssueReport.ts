import { useIssueReport } from './useIssueReport'
import type { ReportLogger } from './useIssueReport'

export function useWhimboxIssueReport(logger: ReportLogger) {
  const { exporting, exportIssueReport } = useIssueReport(logger, {
    label: 'Whimbox',
    fallbackName: 'Whimbox-logs-*.zip',
    exportFn: () => window.hostAPI?.exportWhimboxIssueReport?.(),
  })
  return { exporting, exportWhimboxIssueReport: exportIssueReport }
}

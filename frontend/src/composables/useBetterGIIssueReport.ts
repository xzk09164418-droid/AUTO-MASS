import { useIssueReport } from './useIssueReport'
import type { ReportLogger } from './useIssueReport'

export function useBetterGIIssueReport(logger: ReportLogger) {
  const { exporting, exportIssueReport } = useIssueReport(logger, {
    label: 'BetterGI',
    fallbackName: 'BetterGI-logs-*.zip',
    exportFn: () => window.hostAPI?.exportBetterGIIssueReport?.(),
  })
  return { exporting, exportBetterGIIssueReport: exportIssueReport }
}

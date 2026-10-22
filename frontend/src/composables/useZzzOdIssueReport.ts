import { useIssueReport } from './useIssueReport'
import type { ReportLogger } from './useIssueReport'

export function useZzzOdIssueReport(logger: ReportLogger) {
  const { exporting, exportIssueReport } = useIssueReport(logger, {
    label: 'ZZZ-OD',
    fallbackName: 'ZZZ-OD-logs-*.zip',
    exportFn: () => window.hostAPI?.exportZzzOdIssueReport?.(),
  })
  return { exporting, exportZzzOdIssueReport: exportIssueReport }
}

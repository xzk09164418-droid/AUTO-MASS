import { useIssueReport } from './useIssueReport'
import type { ReportLogger } from './useIssueReport'

export function useOkNteIssueReport(logger: ReportLogger) {
  const { exporting, exportIssueReport } = useIssueReport(logger, {
    label: 'OK-NTE',
    fallbackName: 'OK-NTE-logs-*.zip',
    exportFn: () => window.hostAPI?.exportOkNteIssueReport?.(),
  })
  return { exporting, exportOkNteIssueReport: exportIssueReport }
}

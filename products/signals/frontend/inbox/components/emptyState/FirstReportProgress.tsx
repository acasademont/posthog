import { Link, Spinner } from '@posthog/lemon-ui'

import { TZLabel } from 'lib/components/TZLabel'
import { urls } from 'scenes/urls'

import { ReadonlyRunSurface } from 'products/posthog_ai/frontend/api/readableRun'

import { FirstReportStateApi } from '../../../generated/api.schemas'
import { RunLogContainer } from '../detail/RunLogContainer'

export interface FirstReportProgressProps {
    result: FirstReportStateApi
    notificationEmail?: string | null
}

export function FirstReportProgress({ result, notificationEmail }: FirstReportProgressProps): JSX.Element {
    const messages = {
        pending: ['Checking your project', 'We’re checking which data is available for your first investigation.'],
        running: [
            'Looking for your first report',
            'Follow the investigation below as we look for something useful you can act on.',
        ],
        no_data: [
            'Add data to get started',
            'Self-driving uses your project’s data to find useful insights. Start sending data to PostHog or connect a data warehouse source.',
        ],
        insufficient_data: [
            'More data is needed',
            'There isn’t enough data yet to produce a reliable report. Your sources and scheduled scouts will continue checking as data arrives.',
        ],
        no_actionable_finding: [
            'Your first investigation is complete',
            'We checked your data and didn’t find anything worth reporting yet. Your sources and scheduled scouts will continue checking for useful findings.',
        ],
        incomplete: [
            'Your first investigation couldn’t finish',
            'We couldn’t complete the investigation. Your sources and scheduled scouts will continue checking. Review your connections in settings if data is unavailable.',
        ],
        report_created: [
            'Your first report is ready',
            'Open your inbox to see the finding and its recommended next step.',
        ],
    }
    const [title, description] = messages[result.status]

    return (
        <div className="flex w-full min-w-0 flex-col items-center gap-3 text-center">
            <h2 className="m-0 text-lg font-semibold">{title}</h2>
            <p className="m-0 max-w-xl text-sm text-tertiary">{description}</p>
            {result.started_at ? (
                <span className="text-xs text-tertiary">
                    Started <TZLabel time={result.started_at} />
                </span>
            ) : null}
            {result.task_id && result.task_run_id ? (
                <div className="w-full min-w-0 text-left" aria-label="First report investigation activity">
                    <RunLogContainer>
                        <ReadonlyRunSurface
                            taskId={result.task_id}
                            runId={result.task_run_id}
                            interaction={result.status === 'running' ? 'live' : 'read-only'}
                            threadRowClassName="px-3"
                            threadListClassName="py-3"
                        />
                    </RunLogContainer>
                </div>
            ) : result.status === 'pending' || result.status === 'running' ? (
                <span className="flex items-center gap-2 text-sm text-secondary" role="status">
                    <Spinner className="text-lg" />
                    <span>
                        {result.status === 'pending' ? 'Checking available data…' : 'Starting the investigation…'}
                    </span>
                </span>
            ) : null}
            {result.status === 'insufficient_data' && result.missing_data?.length ? (
                <ul className="m-0 max-w-xl text-left text-sm text-secondary">
                    {result.missing_data.map((item, index) => (
                        <li key={index}>{item}</li>
                    ))}
                </ul>
            ) : null}
            {result.status === 'no_data' ? <Link to={urls.sources()}>Connect a data source</Link> : null}
            {result.status === 'incomplete' ? <Link to={urls.inbox('settings')}>Review connections</Link> : null}
            {result.report_id ? (
                <Link to={urls.inboxReport('reports', result.report_id)}>Open your first report</Link>
            ) : null}
            {notificationEmail && result.status !== 'report_created' ? (
                <p className="m-0 max-w-xl break-words text-sm text-secondary">
                    We’ll also email you at {notificationEmail} when your first report is ready.
                </p>
            ) : null}
        </div>
    )
}

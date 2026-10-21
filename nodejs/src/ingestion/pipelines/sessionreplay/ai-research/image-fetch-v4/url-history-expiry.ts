import { teamMonthKeyExpiresAtMs } from '~/ingestion/pipelines/sessionreplay/ai-research/v4-keys/team-month-keys'
import { explicitFreshnessLifetimeMs } from '~/ingestion/pipelines/sessionreplay/ml-mirror-image-fetch/configuration-policy'

import { HttpCacheMetadata } from './crawl-history'
import { parseV4UrlRef } from './v4-url-ref'

/** A reference is fetched again after the crawl history TTL, or later when the response stays fresh for longer. */
export function urlHistoryExpiresAtMs(nowMs: number, seenTtlSeconds: number, cache?: HttpCacheMetadata): number {
    const minimumNextFetchAtMs = nowMs + seenTtlSeconds * 1000
    const explicitNextFetchAtMs = cache ? nowMs + explicitFreshnessLifetimeMs(cache, nowMs) : 0
    return Math.max(minimumNextFetchAtMs, explicitNextFetchAtMs)
}

/**
 * When the history entry of a reference may go. The entry of a v4 reference stays until the key row of its team month
 * expires, because the lane refreshes the stored image from it.
 */
export function urlHistoryStorageExpiresAtMs(ref: string, nextFetchAtMs: number): number {
    const v4 = parseV4UrlRef(ref)
    return v4 ? teamMonthKeyExpiresAtMs(v4.keyMonth) : nextFetchAtMs
}

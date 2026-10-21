import { urlHistoryExpiresAtMs, urlHistoryStorageExpiresAtMs } from './url-history-expiry'

describe('url history expiry', () => {
    const NOW_MS = Date.parse('2026-10-15T12:00:00Z')
    const TTL_SECONDS = 30 * 24 * 60 * 60

    it('fetches a v4 reference again after the TTL, and keeps its entry as long as its team month key row', () => {
        const nextFetchAtMs = urlHistoryExpiresAtMs(NOW_MS, TTL_SECONDS)

        expect(nextFetchAtMs).toBe(NOW_MS + TTL_SECONDS * 1000)
        expect(urlHistoryStorageExpiresAtMs('imageurl:v4:7:2026-10:aaaaaaaaaaaaaaaaaaaaaa', nextFetchAtMs)).toBe(
            Date.parse('2027-03-01T00:00:00Z')
        )
    })
})

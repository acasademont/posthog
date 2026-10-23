// A breakdown series is labelled `event - value`, with `::` between the values of several breakdowns.
function namesOf(label: string): string[] {
    const lower = label.toLowerCase()
    const at = lower.lastIndexOf(' - ')
    const value = at === -1 ? lower : lower.slice(at + 3)
    return [lower, value, ...value.split('::')]
}

export function isNamedSeries(label: string, names: string[]): boolean {
    const wanted = new Set(names.map((name) => name.trim().toLowerCase()).filter(Boolean))
    return namesOf(label).some((name) => wanted.has(name))
}

import { MOCK_DEFAULT_USER } from 'lib/api.mock'

import { expectLogic } from 'kea-test-utils'

import { FIRST_REPORT_SCOUT_NAME } from 'lib/constants'
import { userLogic } from 'scenes/userLogic'

import { initKeaTests } from '~/test/init'

import { llmSkillsList } from 'products/skills/frontend/generated/api'

import { llmSkillsLogic } from './llmSkillsLogic'

jest.mock('products/skills/frontend/generated/api', () => ({
    llmSkillsList: jest.fn(),
}))

const mockList = llmSkillsList as jest.MockedFunction<typeof llmSkillsList>

describe('llmSkillsLogic', () => {
    let logic: ReturnType<typeof llmSkillsLogic.build>

    beforeEach(() => {
        jest.clearAllMocks()
        initKeaTests()
    })

    afterEach(() => {
        logic?.unmount()
    })

    it.each([false, true])('filters the first-report skill from the UI unless staff=%s', async (isStaff) => {
        userLogic.actions.loadUserSuccess({ ...MOCK_DEFAULT_USER, is_staff: isStaff })
        mockList.mockResolvedValue({
            results: [
                {
                    id: 'first-report',
                    name: FIRST_REPORT_SCOUT_NAME,
                    description: 'First investigation',
                    version: 1,
                    spec_problems: [],
                    category: 'scout',
                    owners: [],
                    outline: [],
                    version_description: null,
                    created_by: {
                        id: 1,
                        uuid: '11111111-1111-4111-8111-111111111111',
                        email: 'alex@example.com',
                        hedgehog_config: null,
                    },
                    created_at: '2026-10-22T12:00:00Z',
                    updated_at: '2026-10-22T12:00:00Z',
                    deleted: false,
                    is_latest: true,
                    latest_version: 1,
                    version_count: 1,
                    first_version_created_at: '2026-10-22T12:00:00Z',
                },
            ],
            count: 1,
        })
        logic = llmSkillsLogic()
        logic.mount()
        await expectLogic(logic).toFinishAllListeners()
        expect(logic.values.skills.results).toHaveLength(isStaff ? 1 : 0)
        expect(logic.values.count).toBe(isStaff ? 1 : 0)
    })

    it.each([
        ['flat list', false],
        ['grouped list', true],
    ])('renders an empty %s when the list response has no body', async (_desc, groupByPrefix) => {
        // The API layer resolves a 204 or an empty body to null, although the generated type says otherwise.
        mockList.mockResolvedValue(null as unknown as Awaited<ReturnType<typeof llmSkillsList>>)
        logic = llmSkillsLogic()
        logic.mount()
        logic.actions.setFilters({ group_by_prefix: groupByPrefix }, true, false)
        await expectLogic(logic).toFinishAllListeners()

        expect(logic.values.skills).toEqual({ results: [], count: 0 })
        expect(logic.values.count).toBe(0)
        expect(logic.values.skillCountLabel).toBe('0 skills')
        expect(logic.values.groupedSkills === null).toBe(!groupByPrefix)
    })
})

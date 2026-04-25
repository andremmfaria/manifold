import { describe, expect, it, vi } from 'vitest'

vi.mock('react-querybuilder', () => ({
  QueryBuilder: (props: Record<string, unknown>) => ({
    type: 'mock-query-builder',
    props,
  }),
}))

import { AlarmRuleBuilder } from '@/features/alarms/AlarmRuleBuilder'

describe('AlarmRuleBuilder', () => {
  it('passes expected fields to query builder', () => {
    const element = AlarmRuleBuilder({
      value: { combinator: 'and', rules: [] },
      onChange: vi.fn(),
    })
    const queryBuilder = (element.props.children as {
      props: {
        fields: Array<{ name: string; label: string }>
        controlClassnames: Record<string, string>
      }
    })

    expect(queryBuilder.props.fields.map((field) => field.label)).toEqual(
      expect.arrayContaining(['Balance', 'Currency']),
    )
    expect(queryBuilder.props.controlClassnames.queryBuilder).toBe('text-sm')
  })
})

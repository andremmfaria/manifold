import { QueryBuilder, RuleGroupType, type ValueEditorType } from 'react-querybuilder'
import 'react-querybuilder/dist/query-builder.css'

interface AlarmRuleBuilderProps {
  value: RuleGroupType | any
  onChange: (v: RuleGroupType | any) => void
}

export function AlarmRuleBuilder({ value, onChange }: AlarmRuleBuilderProps) {
  // Define fields that can be used in rules
  const fields = [
    { name: 'balance', label: 'Balance', inputType: 'number' },
    { name: 'transaction_amount', label: 'Transaction Amount', inputType: 'number' },
    {
      name: 'transaction_type',
      label: 'Transaction Type',
      valueEditorType: 'select' as ValueEditorType,
      values: [
        { name: 'credit', label: 'Credit' },
        { name: 'debit', label: 'Debit' },
      ],
    },
    { name: 'currency', label: 'Currency' },
  ]

  // Wrap in a tokenized container — don't fight querybuilder's internal DOM
  return (
    <div className="rounded-xl border border-border bg-muted/30 p-4">
      <QueryBuilder
        fields={fields}
        query={value as RuleGroupType}
        onQueryChange={onChange as (q: RuleGroupType) => void}
        controlClassnames={{
          queryBuilder: 'text-sm text-foreground',
          ruleGroup: 'bg-card border border-border rounded-lg p-3 mb-3',
          header: 'flex gap-2 mb-2',
          addRule:
            'bg-muted px-2 py-1 rounded text-xs font-medium hover:bg-muted/70 text-foreground',
          addGroup:
            'bg-muted px-2 py-1 rounded text-xs font-medium hover:bg-muted/70 text-foreground',
          removeGroup:
            'bg-destructive/10 text-destructive px-2 py-1 rounded text-xs font-medium hover:bg-destructive/20',
          rule: 'flex gap-2 items-center mb-2',
          fields: 'border border-border bg-background rounded px-2 py-1 text-foreground',
          operators: 'border border-border bg-background rounded px-2 py-1 text-foreground',
          value: 'border border-border bg-background rounded px-2 py-1 text-foreground',
          removeRule:
            'bg-destructive/10 text-destructive px-2 py-1 rounded text-xs font-medium hover:bg-destructive/20 ml-auto',
        }}
      />
    </div>
  )
}

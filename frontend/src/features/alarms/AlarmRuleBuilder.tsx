import { QueryBuilder, RuleGroupType } from 'react-querybuilder'
import 'react-querybuilder/dist/query-builder.css'

interface AlarmRuleBuilderProps {
  value: RuleGroupType | any;
  onChange: (v: RuleGroupType | any) => void;
}

export function AlarmRuleBuilder({ value, onChange }: AlarmRuleBuilderProps) {
  // Define fields that can be used in rules
  const fields = [
    { name: 'balance', label: 'Balance', inputType: 'number' },
    { name: 'transaction_amount', label: 'Transaction Amount', inputType: 'number' },
    { name: 'transaction_type', label: 'Transaction Type', valueEditorType: 'select', values: [{name: 'credit', label: 'Credit'}, {name: 'debit', label: 'Debit'}] },
    { name: 'currency', label: 'Currency' }
  ];

  // Add some basic styling overrides to make it fit with Tailwind
  return (
    <div className="rounded-md border p-4 bg-slate-50">
      <QueryBuilder 
        fields={fields} 
        query={value as RuleGroupType} 
        onQueryChange={onChange as (q: RuleGroupType) => void}
        controlClassnames={{
          queryBuilder: 'text-sm',
          ruleGroup: 'bg-white border rounded-md p-3 mb-3',
          header: 'flex gap-2 mb-2',
          addRule: 'bg-slate-100 px-2 py-1 rounded text-xs font-medium hover:bg-slate-200',
          addGroup: 'bg-slate-100 px-2 py-1 rounded text-xs font-medium hover:bg-slate-200',
          removeGroup: 'bg-red-50 text-red-600 px-2 py-1 rounded text-xs font-medium hover:bg-red-100',
          rule: 'flex gap-2 items-center mb-2',
          fields: 'border rounded px-2 py-1',
          operators: 'border rounded px-2 py-1',
          value: 'border rounded px-2 py-1',
          removeRule: 'bg-red-50 text-red-600 px-2 py-1 rounded text-xs font-medium hover:bg-red-100 ml-auto',
        }}
      />
    </div>
  )
}

export interface DirectDebit {
  id: string
  account_id: string
  provider_direct_debit_id: string | null
  name: string | null
  status: string | null
  source_type: string | null
  confidence: number | null
  previous_payment_amount: string | null
  previous_payment_date: string | null
  created_at: string
  updated_at: string
}

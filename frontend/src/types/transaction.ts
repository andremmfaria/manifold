export type Transaction = {
  id: string
  amount: string | null
  currency?: string | null
  description?: string | null
  merchant_name?: string | null
  transaction_date?: string | null
  account_id?: string | null
  account_display_name?: string | null
  status?: string | null
  transaction_type?: string | null
}

export type Transaction = {
  id: string
  amount: string | null
  currency?: string | null
  description?: string | null
  merchant_name?: string | null
  transaction_date?: string | null
}

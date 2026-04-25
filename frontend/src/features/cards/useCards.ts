import { useQuery } from '@tanstack/react-query'
import { cardsApi } from '@/api/cards'

export function useCards() {
  return useQuery({ queryKey: ['cards'], queryFn: cardsApi.list })
}

export function useCard(cardId: string) {
  return useQuery({ queryKey: ['cards', cardId], queryFn: () => cardsApi.get(cardId) })
}

import { brl } from './util'

/**
 * Etiqueta de preço colada na caixa.
 * Amarela = é o menor preço já visto. Branca = preço atual comum.
 */
export default function Etiqueta({ valor, rotulo, menor = false, tamanho = 'normal', className = '' }) {
  return (
    <span className={`etiqueta ${menor ? 'menor' : 'comum'} ${tamanho} ${className}`}>
      {rotulo && <span className="etiqueta-rotulo">{rotulo}</span>}
      <span className="etiqueta-valor">{brl(valor)}</span>
    </span>
  )
}

/** Variação contra o preço normal (mediana). Texto + seta, nunca só cor. */
export function Variacao({ pct, curto = false }) {
  if (pct == null) return null
  if (Math.abs(pct) < 3) return <span className="variacao neutra">{curto ? 'Preço normal' : 'No preço normal'}</span>
  const abaixo = pct < 0
  return (
    <span className={abaixo ? 'variacao abaixo' : 'variacao acima'}>
      <svg aria-hidden="true" viewBox="0 0 12 12" width="10" height="10">
        <path d={abaixo ? 'M6 10 1.5 4h9z' : 'M6 2l4.5 6h-9z'} fill="currentColor" />
      </svg>
      {Math.abs(pct)}% {abaixo ? 'abaixo' : 'acima'}{curto ? '' : ' do normal'}
    </span>
  )
}

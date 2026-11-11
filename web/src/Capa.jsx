import { useState } from 'react'

/** Classe da faixa de plataforma (cores das caixas reais). */
export const familia = (p = '') =>
  p.startsWith('Switch') ? 'nintendo' : p.startsWith('PS') ? 'playstation' : p.startsWith('Xbox') ? 'xbox' : 'outra'

/** Capa do jogo. Sem imagem, desenha uma caixa com a faixa da plataforma e o nome. */
export default function Capa({ src, nome, plataforma, className = '' }) {
  const [falhou, setFalhou] = useState(false)
  if (src && !falhou) {
    return (
      <img className={`capa ${className}`} src={src} alt={`Capa de ${nome}`}
        loading="lazy" decoding="async" onError={() => setFalhou(true)} />
    )
  }
  const tom = [...(nome || '')].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7)
  return (
    <div className={`capa capa-vazia ${familia(plataforma)} ${className}`}
      style={{ '--tom': tom }} role="img" aria-label={`${nome}, sem capa ainda`}>
      <span className="capa-faixa">{plataforma || 'Jogo'}</span>
      <span className="capa-nome">{nome}</span>
    </div>
  )
}

export function Plataforma({ nome }) {
  if (!nome) return null
  return <span className={`plat ${familia(nome)}`}>{nome}</span>
}

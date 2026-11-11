import { useEffect, useRef, useState } from 'react'

/** Copia texto; no endereço da rede (http, sem clipboard do navegador) usa o jeito antigo. */
async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto)
    return true
  } catch {
    const campo = document.createElement('textarea')
    campo.value = texto
    campo.setAttribute('readonly', '')
    campo.style.cssText = 'position:fixed;top:0;left:0;opacity:0'
    document.body.appendChild(campo)
    campo.select()
    let ok = false
    try { ok = document.execCommand('copy') } catch { ok = false }
    campo.remove()
    return ok
  }
}

/** Código do cupom: clicar nele já copia. */
export default function Cupom({ codigo }) {
  const [estado, setEstado] = useState(null)   // 'ok' | 'erro'
  const relogio = useRef(null)
  useEffect(() => () => clearTimeout(relogio.current), [])

  const clicar = async (e) => {
    e.stopPropagation()
    setEstado((await copiar(codigo)) ? 'ok' : 'erro')
    clearTimeout(relogio.current)
    relogio.current = setTimeout(() => setEstado(null), 1800)
  }

  return (
    <button type="button" className={`cupom${estado === 'ok' ? ' copiado' : ''}`} onClick={clicar}
      title="Clique para copiar o cupom" aria-label={`Copiar o cupom ${codigo}`}>
      <span className="cupom-rotulo">{estado === 'ok' ? '✓ copiado' : estado === 'erro' ? 'não copiou' : 'cupom'}</span>
      {codigo}
      <span className="visualmente-oculto" role="status">{estado === 'ok' ? 'Cupom copiado' : ''}</span>
    </button>
  )
}

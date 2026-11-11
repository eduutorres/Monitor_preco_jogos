import { useEffect, useState } from 'react'
import { api, brl, marcarTelegram, nomeMarca, nomeTipo, rotuloDia, ultimoTelegram } from './util'
import Etiqueta, { Variacao } from './Etiqueta'
import Capa from './Capa'
import Cupom from './Cupom'

export default function Ofertas({ plataforma, tipo, marca, versao, abrir }) {
  const [ofertas, setOfertas] = useState(null)
  const [, redesenhar] = useState(0)            // depois de marcar o Telegram aberto
  const abriuTelegram = (o) => { marcarTelegram(o.jogo_id, o.link_msg); redesenhar((n) => n + 1) }

  useEffect(() => {
    api(`/ofertas?${new URLSearchParams({ limite: 80, plataforma, tipo, marca })}`)
      .then(setOfertas).catch(() => setOfertas([]))
  }, [plataforma, tipo, marca, versao])

  if (!ofertas) return <p className="vazio">Carregando…</p>
  if (!ofertas.length) return <p className="vazio">Nenhuma oferta registrada ainda. Elas aparecem aqui assim que chegam nos canais.</p>

  const dias = []
  for (const o of ofertas) {
    const r = rotuloDia(o.data)
    if (!dias.length || dias[dias.length - 1].rotulo !== r) dias.push({ rotulo: r, itens: [] })
    dias[dias.length - 1].itens.push(o)
  }

  return (
    <div className="feed">
      {dias.map((d) => (
        <section key={d.rotulo} className="dia">
          <h2 className="secao-titulo dia-titulo">{d.rotulo}</h2>
          <ul className="linhas">
            {d.itens.map((o) => (
              <li key={o.id} className="linha">
                <button className="linha-capa" onClick={() => abrir(o.jogo_id)} aria-label={`Ver histórico de ${o.nome}`}>
                  <Capa src={o.capa} nome={o.nome} plataforma={o.plataforma} />
                </button>
                <div className="linha-info">
                  <button className="linha-nome" onClick={() => abrir(o.jogo_id)}>{o.nome}</button>
                  <p className="linha-meta">
                    {o.marca && <span className="selo-marca">{nomeMarca(o.marca)}</span>}
                    {o.tipo && o.tipo !== 'jogo' && <span className="selo-tipo">{nomeTipo(o.tipo)}</span>}
                    {o.plataforma || 'Plataforma ?'}, {o.loja || 'loja ?'}
                    {o.pix ? ', no PIX' : ''}{o.frete_gratis ? ', frete grátis' : ''}
                    {o.prevenda ? ', pré-venda' : ''}
                    {o.cupom && <Cupom codigo={o.cupom} />}
                    {!o.ativo && <span className="esgotou">esgotou</span>}
                  </p>
                  <Variacao pct={o.vs_mediana} />
                </div>
                <div className="linha-preco">
                  <Etiqueta valor={o.preco} menor={o.menor_ate_entao}
                    rotulo={o.menor_ate_entao ? 'menor já visto' : null} />
                  {o.preco_de && <s className="preco-de">{brl(o.preco_de)}</s>}
                </div>
                <div className="linha-acoes">
                  {o.link && <a className="botao" href={o.link} target="_blank" rel="noreferrer">Abrir na loja</a>}
                  {o.link_msg && (
                    <a className="botao secundario" href={o.link_msg} target="_blank" rel="noreferrer"
                      onClick={() => abriuTelegram(o)} onAuxClick={() => abriuTelegram(o)}>
                      Telegram
                    </a>
                  )}
                  {o.link_msg && ultimoTelegram(o.jogo_id) === o.link_msg && <span className="ultimo-aberto">último aberto</span>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

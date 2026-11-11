import { useEffect, useState } from 'react'
import { api, brl, haQuanto, nomeMarca, nomeTipo } from './util'
import Etiqueta, { Variacao } from './Etiqueta'
import Capa from './Capa'

const CURTO = {
  fisico: 'Mais barato que o digital',
  digital: 'Digital está mais barato',
}

const POR_VEZ = 120

const ORDENS = [
  ['recentes', 'Mais recentes'],
  ['desconto', 'Maior queda'],
  ['preco', 'Mais baratos'],
  ['nome', 'A–Z'],
]

export default function Jogos({ busca, plataforma, tipo, marca, versao, abrir }) {
  const [ordem, setOrdem] = useState('recentes')
  const [jogos, setJogos] = useState(null)
  // 1.400+ capas de uma vez travavam o celular: mostra por partes
  const [limite, setLimite] = useState(POR_VEZ)
  useEffect(() => { setLimite(POR_VEZ) }, [busca, plataforma, ordem, tipo, marca])

  useEffect(() => {
    const t = setTimeout(() => {
      const p = new URLSearchParams({ q: busca, plataforma, ordem, tipo, marca })
      api(`/jogos?${p}`).then(setJogos).catch(() => setJogos([]))
    }, 160)
    return () => clearTimeout(t)
  }, [busca, plataforma, ordem, tipo, marca, versao])

  if (!jogos) return <p className="vazio">Carregando…</p>

  const naEtiqueta = busca || marca ? [] : jogos.filter((j) => j.no_menor_preco && j.ofertas >= 3)

  return (
    <>
      {naEtiqueta.length > 0 && (
        <section className="vitrine" aria-labelledby="vitrine-titulo">
          <div className="secao-topo">
            <h2 id="vitrine-titulo" className="secao-titulo">No menor preço agora</h2>
            <p className="secao-nota">A última oferta destes jogos é a mais barata que já apareceu.</p>
          </div>
          <ul className="vitrine-lista">
            {naEtiqueta.map((j) => <li key={j.id}><Caixa jogo={j} abrir={abrir} /></li>)}
          </ul>
        </section>
      )}

      <section aria-labelledby="todos-titulo">
        <div className="secao-topo">
          <h2 id="todos-titulo" className="secao-titulo">
            {busca ? `${jogos.length} resultado${jogos.length === 1 ? '' : 's'} para “${busca}”`
              : marca ? `${nomeMarca(marca)} (${jogos.length})` : 'Todos os jogos'}
          </h2>
          {!busca && jogos.length > 1 && (
            <label className="ordem">
              <span className="visualmente-oculto">Ordenar por</span>
              <select value={ordem} onChange={(e) => setOrdem(e.target.value)}>
                {ORDENS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
              </select>
            </label>
          )}
        </div>

        {jogos.length === 0 ? (
          <p className="vazio">
            {busca
              ? 'Esse jogo ainda não apareceu nos canais. Coloque na lista de desejos para ser avisado quando aparecer.'
              : marca ? 'Nenhum item marcado assim com esses filtros.'
                : 'Nenhuma oferta registrada ainda. Deixe o monitor rodando e elas aparecem aqui.'}
          </p>
        ) : (
          <>
            <ul className="prateleira">
              {jogos.slice(0, limite).map((j) => <li key={j.id}><Caixa jogo={j} abrir={abrir} /></li>)}
            </ul>
            {jogos.length > limite && (
              <div className="mais">
                <button className="botao secundario" onClick={() => setLimite((n) => n + POR_VEZ)}>
                  Mostrar mais ({jogos.length - limite} restantes)
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </>
  )
}

/** Uma caixa de jogo na prateleira, com a etiqueta de preço colada. */
function Caixa({ jogo: j, abrir }) {
  const noMenor = j.no_menor_preco && j.ofertas > 1
  return (
    <button className="caixa" onClick={() => abrir(j.id)}>
      <span className="caixa-capa">
        <Capa src={j.capa} nome={j.nome} plataforma={j.plataforma} />
        <Etiqueta valor={j.ultimo_preco} menor={noMenor} rotulo={noMenor ? 'menor já visto' : null}
          className="caixa-etiqueta" />
      </span>
      <span className="caixa-nome">
        {j.marca && <span className="selo-marca">{nomeMarca(j.marca)}</span>}
        {j.tipo && j.tipo !== 'jogo' && <span className="selo-tipo">{nomeTipo(j.tipo)}</span>}
        {j.nome}
      </span>
      <span className="caixa-meta">
        {j.plataforma || 'Plataforma ?'}, {j.ultima_loja || 'loja ?'}, {haQuanto(j.ultima_data)}
      </span>
      {!noMenor && j.ofertas > 1 && <span className="caixa-menor">Menor já visto: {brl(j.menor_preco)}</span>}
      {j.ofertas >= 3 && <Variacao pct={j.vs_mediana} curto />}
      {CURTO[j.veredito?.tipo] && <span className={`caixa-digital ${j.veredito.tipo}`}>{CURTO[j.veredito.tipo]}</span>}
    </button>
  )
}

import { useState } from 'react'
import { api, brl, haQuanto } from './util'

const SELO = {
  fisico: 'Vale o físico',
  fisico_hoje: 'Físico mais barato hoje',
  digital: 'Digital mais barato',
  empate: 'Mesmo preço',
}

/** Seção "Físico ou digital?" do detalhe do jogo. */
export default function Digital({ jogo, aoAtualizar, aoCorrigir }) {
  const d = jogo.digital
  const v = jogo.veredito
  const [editando, setEditando] = useState(false)
  const [link, setLink] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState('')

  const atualizar = async (url) => {
    setOcupado(true); setErro('')
    try {
      aoAtualizar(await api(`/jogos/${jogo.id}/digital`, { method: 'POST', body: url ? { url } : {} }))
      setEditando(false); setLink('')
    } catch (e) { setErro(e.message) }
    setOcupado(false)
  }

  const temPreco = d && d.preco_atual != null

  // a página do Deku Deals é de outro console: o jogo provavelmente foi cadastrado no console errado
  const corrigirConsole = async (plataforma) => {
    setOcupado(true); setErro('')
    try {
      aoCorrigir(await api(`/jogos/${jogo.id}/editar`, { method: 'POST', body: { plataforma } }))
    } catch (e) { setErro(e.message); setOcupado(false) }
  }

  return (
    <section className="fisdig" aria-labelledby="fisdig-titulo">
      <div className="fisdig-topo">
        <h3 id="fisdig-titulo" className="ficha-titulo">Físico ou digital?</h3>
        {v && <span className={`selo selo-${v.tipo}`}>{SELO[v.tipo]}</span>}
      </div>

      {temPreco ? (
        <>
          {v && <p className="fisdig-texto">{v.texto}</p>}
          <Comparacao jogo={jogo} />
        </>
      ) : (
        <p className="fisdig-texto">
          {d?.erro || 'Ainda buscando o preço digital deste jogo no Deku Deals. Isso acontece sozinho em alguns minutos.'}
        </p>
      )}
      {!temPreco && d?.outras?.length > 0 && (
        <div className="fisdig-console">
          {d.outras.map((p) => (
            <button key={p} className="botao" onClick={() => corrigirConsole(p)} disabled={ocupado}>
              {ocupado ? 'Corrigindo…' : `É de ${p}`}
            </button>
          ))}
          <span className="fisdig-fonte">Muda o console deste jogo{jogo.ofertas > 1 ? ` e das ${jogo.ofertas} ofertas` : ''}.</span>
        </div>
      )}

      <div className="fisdig-rodape">
        {temPreco && (
          <p className="fisdig-fonte">
            Preço digital da loja oficial no Brasil, pelo Deku Deals, {d.atualizado ? `consultado ${haQuanto(d.atualizado)}` : ''}.
          </p>
        )}
        {temPreco && d.erro && <p className="fisdig-fonte">A última consulta falhou: {d.erro} Os preços acima são da consulta anterior.</p>}
        <div className="fisdig-acoes">
          {d?.url && <a className="botao secundario" href={d.url} target="_blank" rel="noreferrer">Ver no Deku Deals</a>}
          {temPreco && (
            <button className="botao discreto" onClick={() => atualizar()} disabled={ocupado}>
              {ocupado ? 'Atualizando…' : 'Atualizar agora'}
            </button>
          )}
          {!editando && (
            <button className="botao discreto" onClick={() => setEditando(true)}>
              {d?.url ? 'Usar outro link' : 'Colar link do Deku Deals'}
            </button>
          )}
        </div>
        {editando && (
          <form className="fisdig-link" onSubmit={(e) => { e.preventDefault(); atualizar(link) }}>
            <label className="campo">
              <span>Link da página do jogo no Deku Deals</span>
              <input type="url" value={link} onChange={(e) => setLink(e.target.value)} required autoFocus
                placeholder="https://www.dekudeals.com/items/..." />
            </label>
            <button className="botao" type="submit" disabled={ocupado}>{ocupado ? 'Buscando…' : 'Salvar link'}</button>
            <button className="botao discreto" type="button" onClick={() => setEditando(false)}>Cancelar</button>
          </form>
        )}
        {erro && <p className="aviso-erro" role="alert">{erro}</p>}
      </div>
    </section>
  )
}

/** Duas faixas na mesma régua: do menor preço já visto até o preço de agora. */
function Comparacao({ jogo }) {
  const d = jogo.digital
  const linhas = [
    { nome: 'Físico', sub: 'nos seus canais', agora: jogo.ultimo_preco, menor: jogo.menor_preco },
    { nome: 'Digital', sub: 'loja oficial', agora: d.preco_atual, menor: d.menor_preco ?? d.preco_atual },
  ]
  const max = Math.max(...linhas.map((l) => l.agora), d.msrp || 0) * 1.06
  const pct = (v) => `${(v / max) * 100}%`

  return (
    <div className="regua" role="table" aria-label="Comparação de preços físico e digital">
      <div className="regua-legenda" aria-hidden="true">
        <span><i className="ponto agora" /> preço de agora</span>
        <span><i className="ponto menor" /> menor já visto</span>
      </div>
      {linhas.map((l) => (
        <div className="regua-linha" role="row" key={l.nome}>
          <div className="regua-nome" role="rowheader">
            <strong>{l.nome}</strong>
            <span>{l.sub}</span>
          </div>
          <div className="regua-trilho" role="cell" aria-label={`${l.nome}: agora ${brl(l.agora)}, menor já visto ${brl(l.menor)}`}>
            <span className="regua-faixa" style={{ left: pct(l.menor), width: `calc(${pct(l.agora)} - ${pct(l.menor)})` }} />
            <span className="ponto menor" style={{ left: pct(l.menor) }} />
            <span className="ponto agora" style={{ left: pct(l.agora) }} />
          </div>
          <div className="regua-valores" role="cell">
            <strong>{brl(l.agora)}</strong>
            <span>menor {brl(l.menor)}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

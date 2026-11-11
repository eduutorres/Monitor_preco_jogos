import { useEffect, useState } from 'react'
import { api, brl, haQuanto } from './util'
import Capa, { Plataforma } from './Capa'

export default function Desejos({ versao, aoMudar, abrir }) {
  const [desejos, setDesejos] = useState(null)
  const [texto, setTexto] = useState('')
  const [alvo, setAlvo] = useState('')
  const [erro, setErro] = useState('')

  useEffect(() => {
    api('/desejos').then(setDesejos).catch(() => setDesejos([]))
  }, [versao])

  const adicionar = async (e) => {
    e.preventDefault()
    try {
      setDesejos(await api('/desejos', { method: 'POST', body: { texto, preco_alvo: alvo } }))
      setTexto(''); setAlvo(''); setErro(''); aoMudar()
    } catch (err) { setErro(err.message) }
  }

  const remover = async (id) => {
    setDesejos(await api(`/desejos/${id}`, { method: 'DELETE' }))
    aoMudar()
  }

  const ordenados = desejos ? [...desejos].sort((a, b) => b.atingiu - a.atingiu) : null

  return (
    <div className="desejos">
      <form className="form-desejo" onSubmit={adicionar}>
        <div className="form-texto">
          <h2 className="secao-titulo">Adicionar um jogo</h2>
          <p className="secao-nota">
            Quando ele aparecer pelo seu preço ou menos, você recebe um aviso no Telegram.
            Para uma plataforma só, escreva junto: <em>Elden Ring PS5</em>.
          </p>
        </div>
        <div className="form-campos">
          <label className="campo campo-nome">
            <span>Jogo</span>
            <input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Mario Kart World" required />
          </label>
          <label className="campo campo-preco">
            <span>Quero pagar até</span>
            <span className="campo-moeda">
              <span aria-hidden="true">R$</span>
              <input value={alvo} onChange={(e) => setAlvo(e.target.value)} inputMode="decimal" placeholder="300" required
                aria-label="Preço máximo em reais" />
            </span>
          </label>
          <button className="botao" type="submit">Adicionar à lista</button>
        </div>
        {erro && <p className="aviso-erro" role="alert">{erro}</p>}
      </form>

      {ordenados && !ordenados.length && (
        <p className="vazio">Sua lista está vazia. Adicione um jogo acima para começar a receber avisos.</p>
      )}

      <ul className="linhas">
        {ordenados?.map((d) => {
          const r = d.melhor_recente
          const jogoId = d.jogos[0]?.id
          return (
            <li key={d.id} className={d.atingiu ? 'linha desejo atingiu' : 'linha desejo'}>
              <button className="linha-capa" onClick={() => jogoId && abrir(jogoId)} disabled={!jogoId}
                aria-label={jogoId ? `Ver histórico de ${d.texto}` : `${d.texto} ainda não apareceu`}>
                <Capa src={d.capa} nome={d.jogos[0]?.nome || d.texto} plataforma={d.plataforma || d.jogos[0]?.plataforma} />
              </button>
              <div className="linha-info">
                {jogoId
                  ? <button className="linha-nome" onClick={() => abrir(jogoId)}>{d.texto}</button>
                  : <span className="linha-nome">{d.texto}</span>}
                <p className="linha-meta">
                  {d.plataforma && <Plataforma nome={d.plataforma} />}
                  {d.menor_preco != null ? <>Menor já visto: {brl(d.menor_preco)}</> : 'Ainda não apareceu nos canais'}
                </p>
                <p className="desejo-status">
                  {d.atingiu ? (
                    <>
                      <svg aria-hidden="true" viewBox="0 0 16 16" width="15" height="15"><path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                      Chegou no seu preço: {brl(r.preco)} na {r.loja || 'loja'}, {haQuanto(r.data)}
                    </>
                  ) : r ? (
                    <>Melhor dos últimos 30 dias: {brl(r.preco)}. Faltam {brl(r.preco - d.preco_alvo)}.</>
                  ) : d.jogos.length ? 'Sem ofertas nos últimos 30 dias' : null}
                </p>
              </div>
              <div className="linha-preco">
                <span className="alvo">
                  <span className="alvo-rotulo">seu alvo</span>
                  <span className="alvo-valor">{brl(d.preco_alvo)}</span>
                </span>
              </div>
              <div className="linha-acoes">
                {d.atingiu && r.link && <a className="botao" href={r.link} target="_blank" rel="noreferrer">Abrir na loja</a>}
                <button className="botao discreto" onClick={() => remover(d.id)} aria-label={`Remover ${d.texto} da lista`}>Remover</button>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

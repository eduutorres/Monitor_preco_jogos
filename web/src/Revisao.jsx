import { useEffect, useState } from 'react'
import { api, brl, haQuanto, nomeTipo } from './util'
import Capa from './Capa'

/** Fila do que precisa da sua atenção: possíveis repetidos, sem plataforma e sem capa. */
export default function Revisao({ versao, abrir, aoMudar }) {
  const [fila, setFila] = useState(null)
  const [ocupado, setOcupado] = useState(null)   // chave do item sendo resolvido
  const [aviso, setAviso] = useState('')
  const [erro, setErro] = useState('')
  const [verDigital, setVerDigital] = useState(30)   // a lista sem preço digital é longa: 30 por vez

  useEffect(() => {
    api('/revisao').then(setFila).catch(() => setFila({ repetidos: [], sem_plataforma: [], sem_digital: [], sem_capa: [] }))
  }, [versao])

  const fazer = async (chave, acao, texto) => {
    setOcupado(chave); setErro('')
    try {
      await acao()
      setFila(await api('/revisao'))
      setAviso(texto)
      aoMudar()
    } catch (err) { setErro(err.message) } finally { setOcupado(null) }
  }
  const dispensar = (chave, texto) =>
    fazer(chave, () => api('/revisao/ok', { method: 'POST', body: { chave } }), texto)
  const juntar = (par, fica, sai) =>
    fazer(par.chave, () => api(`/jogos/${fica.id}/juntar`, { method: 'POST', body: { com: sai.id } }),
      `Juntado: as ${sai.ofertas} ofertas de “${sai.nome}” agora estão em “${fica.nome}”.`)

  if (!fila) return <p className="vazio">Carregando…</p>
  const total = fila.repetidos.length + fila.sem_plataforma.length + (fila.sem_digital?.length || 0) + fila.sem_capa.length

  return (
    <div className="revisao">
      <div className="secao-topo">
        <h2 className="secao-titulo">Revisar</h2>
        <p className="secao-nota">
          O que o monitor não conseguiu resolver sozinho. O que você dispensar aqui não volta para a fila.
        </p>
      </div>
      {aviso && <p className="revisao-aviso" role="status">{aviso}</p>}
      {erro && <p className="aviso-erro" role="alert">{erro}</p>}
      {total === 0 && <p className="vazio">Nada para revisar agora.</p>}

      {fila.repetidos.length > 0 && (
        <section className="revisao-grupo" aria-labelledby="rev-repetidos">
          <h3 id="rev-repetidos" className="ficha-titulo">
            Possíveis repetidos <span className="titulo-num">{fila.repetidos.length}</span>
          </h3>
          <p className="editor-nota">
            Nomes muito parecidos no mesmo console. Se forem o mesmo, escolha com qual ficar: as ofertas do outro
            passam para ele, e esse nome passa a cair no lugar certo daqui pra frente.
          </p>
          <ul className="revisao-lista">
            {fila.repetidos.map((par) => {
              const [a, b] = par.jogos
              return (
                <li key={par.chave} className="par" aria-busy={ocupado === par.chave}>
                  <div className="par-jogos">
                    {[[a, b], [b, a]].map(([este, outro]) => (
                      <div key={este.id} className="par-jogo">
                        <MiniJogo jogo={este} abrir={abrir} />
                        <button className="botao secundario" disabled={!!ocupado}
                          onClick={() => juntar(par, este, outro)}>
                          Ficar com este
                        </button>
                      </div>
                    ))}
                  </div>
                  <button className="botao discreto" disabled={!!ocupado}
                    onClick={() => dispensar(par.chave, `Ok, “${a.nome}” e “${b.nome}” continuam separados.`)}>
                    São diferentes
                  </button>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {fila.sem_plataforma.length > 0 && (
        <section className="revisao-grupo" aria-labelledby="rev-sem-plat">
          <h3 id="rev-sem-plat" className="ficha-titulo">
            Sem plataforma <span className="titulo-num">{fila.sem_plataforma.length}</span>
          </h3>
          <p className="editor-nota">A mensagem não dizia o console. Abra e use “Corrigir”, ou dispense se for de vários consoles.</p>
          <ul className="revisao-lista">
            {fila.sem_plataforma.map((j) => (
              <li key={j.chave} className="revisao-item" aria-busy={ocupado === j.chave}>
                <MiniJogo jogo={j} abrir={abrir} />
                <div className="revisao-acoes">
                  <button className="botao secundario" onClick={() => abrir(j.id)}>Abrir e corrigir</button>
                  <button className="botao discreto" disabled={!!ocupado}
                    onClick={() => dispensar(j.chave, `“${j.nome}” fica sem plataforma.`)}>
                    Está certo assim
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {fila.sem_digital?.length > 0 && (
        <section className="revisao-grupo" aria-labelledby="rev-sem-digital">
          <h3 id="rev-sem-digital" className="ficha-titulo">
            Sem preço digital <span className="titulo-num">{fila.sem_digital.length}</span>
          </h3>
          <p className="editor-nota">
            O Deku Deals não achou o jogo, ou achou só em outro console. Abra o jogo e cole o link da página certa
            em “Colar link do Deku Deals”. Se o jogo não tem versão digital, dispense.
          </p>
          <ul className="revisao-lista">
            {fila.sem_digital.slice(0, verDigital).map((j) => (
              <li key={j.chave} className="revisao-item" aria-busy={ocupado === j.chave}>
                <MiniJogo jogo={j} abrir={abrir} />
                <p className="revisao-motivo">
                  {j.erro}
                  {j.url && <> <a href={j.url} target="_blank" rel="noreferrer">Página usada</a></>}
                </p>
                <div className="revisao-acoes">
                  <button className="botao secundario" onClick={() => abrir(j.id)}>Abrir e colar link</button>
                  <button className="botao discreto" disabled={!!ocupado}
                    onClick={() => dispensar(j.chave, `“${j.nome}” fica sem preço digital.`)}>
                    Não tem digital
                  </button>
                </div>
              </li>
            ))}
          </ul>
          {fila.sem_digital.length > verDigital && (
            <button className="botao secundario revisao-mais" onClick={() => setVerDigital((n) => n + 30)}>
              Mostrar mais ({fila.sem_digital.length - verDigital} restantes)
            </button>
          )}
        </section>
      )}

      {fila.sem_capa.length > 0 && (
        <section className="revisao-grupo" aria-labelledby="rev-sem-capa">
          <h3 id="rev-sem-capa" className="ficha-titulo">
            Sem capa <span className="titulo-num">{fila.sem_capa.length}</span>
          </h3>
          <p className="editor-nota">A mensagem veio sem foto. Abra o item e cole uma capa (Ctrl+V).</p>
          <ul className="revisao-lista">
            {fila.sem_capa.map((j) => (
              <li key={j.chave} className="revisao-item" aria-busy={ocupado === j.chave}>
                <MiniJogo jogo={j} abrir={abrir} />
                <div className="revisao-acoes">
                  <button className="botao secundario" onClick={() => abrir(j.id)}>Abrir</button>
                  <button className="botao discreto" disabled={!!ocupado}
                    onClick={() => dispensar(j.chave, `“${j.nome}” fica sem capa.`)}>
                    Deixar sem capa
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function MiniJogo({ jogo: j, abrir }) {
  return (
    <div className="mini">
      <button className="mini-capa" onClick={() => abrir(j.id)} aria-label={`Abrir ${j.nome}`}>
        <Capa src={j.capa} nome={j.nome} plataforma={j.plataforma} />
      </button>
      <div className="mini-info">
        <button className="linha-nome" onClick={() => abrir(j.id)}>{j.nome}</button>
        <p className="linha-meta">
          {j.tipo && j.tipo !== 'jogo' && <span className="selo-tipo">{nomeTipo(j.tipo)}</span>}
          {j.plataforma || 'Plataforma ?'}, {j.ofertas} {j.ofertas === 1 ? 'oferta' : 'ofertas'}
        </p>
        {j.ultima_data && (
          <p className="linha-meta">Última: {brl(j.ultimo_preco)}, {j.ultima_loja || 'loja ?'}, {haQuanto(j.ultima_data)}</p>
        )}
      </div>
    </div>
  )
}

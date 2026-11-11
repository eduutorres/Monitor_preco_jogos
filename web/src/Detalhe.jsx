import { Fragment, useEffect, useRef, useState } from 'react'
import { api, brl, dataCompleta, dataTabela, haQuanto, marcarTelegram, nomeTipo, ultimoTelegram } from './util'
import Etiqueta, { Variacao } from './Etiqueta'
import Capa, { Plataforma } from './Capa'
import Grafico from './Grafico'
import Digital from './Digital'
import Cupom from './Cupom'
import { ConfirmarCapa, EditarCapa, EditarJogo, ExcluirJogo, imagemDaAreaDeTransferencia, imagemDoEventoColar, MoverOferta } from './Edicao'

/** Painel lateral com tudo sobre um jogo. Fecha com Esc, no X ou clicando fora. */
export default function Detalhe({ id, versao, aoFechar, abrir, aoMudar, plataformas }) {
  const [jogo, setJogo] = useState(null)
  const fechar = useRef(null)
  const gaveta = useRef(null)
  const aoFecharAtual = useRef(aoFechar)
  useEffect(() => { aoFecharAtual.current = aoFechar })

  useEffect(() => {
    api(`/jogos/${id}`).then(setJogo).catch(() => setJogo(null))
  }, [id, versao])

  // Só ao abrir a gaveta. Antes isto dependia de aoFechar, que muda a cada atualização automática
  // (1x por minuto): o foco voltava para o X e a gaveta pulava para o topo.
  useEffect(() => {
    const tecla = (e) => e.key === 'Escape' && aoFecharAtual.current()
    document.addEventListener('keydown', tecla)
    document.body.classList.add('travado')
    return () => { document.removeEventListener('keydown', tecla); document.body.classList.remove('travado') }
  }, [])

  // Outro jogo aberto (ex.: depois de juntar ou mover): começa do topo
  useEffect(() => {
    if (gaveta.current) gaveta.current.scrollTop = 0
    fechar.current?.focus({ preventScroll: true })
  }, [id])

  const pronto = jogo && jogo.id === id

  return (
    <div className="gaveta-fundo" onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}>
      <aside ref={gaveta} className="gaveta" role="dialog" aria-modal="true" aria-label={pronto ? jogo.nome : 'Carregando jogo'}>
        <button ref={fechar} className="gaveta-fechar" onClick={aoFechar} aria-label="Fechar">
          <svg aria-hidden="true" viewBox="0 0 16 16" width="16" height="16">
            <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>

        {!pronto ? <p className="vazio">Carregando…</p> : (
          <Conteudo key={jogo.id} jogo={jogo} aoAtualizar={setJogo} plataformas={plataformas}
            aoCorrigir={(novo) => {
              // depois de juntar/mover, o jogo aberto pode ter mudado de id (ou deixado de existir)
              aoMudar()
              if (novo.id !== id) abrir(novo.id)
              else setJogo(novo)
            }}
            recarregar={() => { aoMudar(); api(`/jogos/${id}`).then(setJogo).catch(() => aoFechar()) }}
            aoExcluir={() => { aoMudar(); aoFechar() }} />
        )}
      </aside>
    </div>
  )
}

function Conteudo({ jogo, aoAtualizar, plataformas, aoCorrigir, recarregar, aoExcluir }) {
  const historico = [...jogo.historico].reverse()
  const [editando, setEditando] = useState(null)   // 'jogo' | 'capa' | id da oferta sendo movida
  // último Telegram aberto DESTE jogo (aqui ou na aba Ofertas)
  const [ultimo, setUltimo] = useState(() => ultimoTelegram(jogo.id))
  const abriuTelegram = (link) => { marcarTelegram(jogo.id, link); setUltimo(link) }
  const opcoes = plataformas?.length ? plataformas : ['Switch 2', 'Switch', 'PS5', 'PS4']

  // várias ofertas marcadas para mover juntas (Shift + clique marca um intervalo)
  const [marcadas, setMarcadas] = useState(() => new Set())
  const ultimoClique = useRef(null)
  const marcar = (indice, e) => {
    const id = historico[indice].id
    const ligar = !marcadas.has(id)
    const novas = new Set(marcadas)
    const de = e.nativeEvent.shiftKey && ultimoClique.current != null ? Math.min(ultimoClique.current, indice) : indice
    const ate = e.nativeEvent.shiftKey && ultimoClique.current != null ? Math.max(ultimoClique.current, indice) : indice
    for (let i = de; i <= ate; i++) ligar ? novas.add(historico[i].id) : novas.delete(historico[i].id)
    ultimoClique.current = indice
    setMarcadas(novas)
  }
  const todas = marcadas.size > 0 && marcadas.size === historico.length
  const marcarTodas = () => setMarcadas(todas ? new Set() : new Set(historico.map((o) => o.id)))
  const limparMarcadas = () => { setMarcadas(new Set()); if (editando === 'varias') setEditando(null) }

  // Colar capa: Ctrl+V com o jogo aberto (fora de campos de texto) ou o botão "Colar capa"
  const [colada, setColada] = useState(null)
  const [erroColar, setErroColar] = useState('')
  useEffect(() => {
    if (editando === 'capa') return undefined          // o editor de capa cuida do Ctrl+V dele
    const colar = (e) => {
      if (e.target.closest?.('input, textarea, [contenteditable]')) return
      const leitura = imagemDoEventoColar(e)
      if (!leitura) return
      e.preventDefault()
      leitura.then((img) => { setErroColar(''); setColada(img) }).catch((err) => setErroColar(err.message))
    }
    document.addEventListener('paste', colar)
    return () => document.removeEventListener('paste', colar)
  }, [editando])
  const colarPeloBotao = async () => {
    setErroColar('')
    try { setColada(await imagemDaAreaDeTransferencia()) } catch (err) { setErroColar(err.message) }
  }

  const ofertaMovida = ({ origem, destino }) => {
    setEditando(null)
    setMarcadas(new Set())
    if (origem == null) aoCorrigir({ id: destino })  // era a última oferta: o jogo sumiu, abre o destino
    else recarregar()
  }
  const varia = jogo.ofertas >= 3 ? jogo.vs_mediana : null

  // "Já tenho" / "Não me interessa" (clicar no marcado desfaz)
  const [marcando, setMarcando] = useState(false)
  const [erroMarca, setErroMarca] = useState('')
  const marcarJogo = async (m) => {
    setMarcando(true); setErroMarca('')
    try {
      aoAtualizar(await api(`/jogos/${jogo.id}/marcar`, { method: 'POST', body: { marca: jogo.marca === m ? null : m } }))
      recarregar()
    } catch (err) { setErroMarca(err.message) } finally { setMarcando(false) }
  }

  return (
    <>
      <header className="ficha">
        <div>
          <div className="ficha-capa">
            <Capa src={jogo.capa} nome={jogo.nome} plataforma={jogo.plataforma} />
          </div>
          <div className="ficha-capa-acoes">
            <button className="botao discreto ficha-editar" onClick={() => setEditando(editando === 'capa' ? null : 'capa')}
              aria-expanded={editando === 'capa'}>
              Trocar capa
            </button>
            <button className="botao discreto ficha-editar" onClick={colarPeloBotao}
              title="Cole uma imagem copiada (ou aperte Ctrl+V com o jogo aberto)">
              Colar capa
            </button>
          </div>
        </div>
        <div className="ficha-info">
          <div className="ficha-plat">
            {jogo.tipo !== 'jogo' && <span className="selo-tipo">{nomeTipo(jogo.tipo)}</span>}
            <Plataforma nome={jogo.plataforma} />
            <button className="botao discreto" onClick={() => setEditando(editando === 'jogo' ? null : 'jogo')}
              aria-expanded={editando === 'jogo'}>
              Corrigir
            </button>
            <button className="botao discreto" onClick={() => setEditando(editando === 'excluir' ? null : 'excluir')}
              aria-expanded={editando === 'excluir'}>
              Excluir jogo
            </button>
          </div>
          <h2 className="ficha-nome">{jogo.nome}</h2>
          <p className="ficha-sub">
            {jogo.ofertas} {jogo.ofertas === 1 ? 'oferta registrada' : 'ofertas registradas'} desde {dataCompleta(jogo.historico[0].data)}
          </p>
          <Etiqueta valor={jogo.menor_preco} menor tamanho="grande" rotulo="menor já visto" />
          <p className="ficha-onde">
            Na {jogo.menor_loja || 'loja não informada'}, em {dataCompleta(jogo.menor_data)}.
            {jogo.no_menor_preco && jogo.ofertas > 1 && <strong> É o preço de agora.</strong>}
          </p>
          <div className="ficha-marca" role="group" aria-label="Esconder das listas">
            {[['tenho', 'Já tenho'], ['ignorar', 'Não me interessa']].map(([m, nome]) => (
              <button key={m} className={jogo.marca === m ? 'chip ativo' : 'chip'} aria-pressed={jogo.marca === m}
                disabled={marcando} onClick={() => marcarJogo(m)}>
                {jogo.marca === m && '✓ '}{nome}
              </button>
            ))}
          </div>
          {jogo.marca && (
            <p className="ficha-marca-nota">
              Fora das listas e sem alertas de preço (a lista de desejos ainda avisa). Clique de novo para desfazer.
            </p>
          )}
          {erroMarca && <p className="aviso-erro" role="alert">{erroMarca}</p>}
        </div>
      </header>

      {erroColar && <p className="aviso-erro colar-erro" role="alert">{erroColar}</p>}
      {colada && (
        <ConfirmarCapa jogo={jogo} imagem={colada} aoCancelar={() => setColada(null)}
          aoSalvar={(novo) => { setColada(null); aoAtualizar(novo); recarregar() }} />
      )}
      {editando === 'jogo' && (
        <EditarJogo jogo={jogo} plataformas={opcoes} aoCancelar={() => setEditando(null)}
          aoSalvar={(novo) => { setEditando(null); aoCorrigir(novo) }} />
      )}
      {editando === 'excluir' && (
        <ExcluirJogo jogo={jogo} aoExcluir={aoExcluir} aoCancelar={() => setEditando(null)} />
      )}
      {editando === 'capa' && (
        <EditarCapa jogo={jogo} aoCancelar={() => setEditando(null)}
          aoSalvar={(novo) => { aoAtualizar(novo); recarregar() }} />
      )}

      <dl className="numeros">
        <div>
          <dt>Última oferta</dt>
          <dd className="numeros-valor">{brl(jogo.ultimo_preco)}</dd>
          <dd>{jogo.ultima_loja || 'Loja ?'}, {haQuanto(jogo.ultima_data)}</dd>
          {varia != null && <dd><Variacao pct={varia} /></dd>}
        </div>
        <div>
          <dt>Preço normal</dt>
          <dd className="numeros-valor">{brl(jogo.mediana)}</dd>
          <dd>Mediana de todas as ofertas</dd>
        </div>
        {jogo.ultimo_link && (
          <div className="numeros-acao">
            <a className="botao" href={jogo.ultimo_link} target="_blank" rel="noreferrer">Abrir a última oferta</a>
          </div>
        )}
      </dl>

      {jogo.tipo === 'jogo' && (
        // recarregar() avisa o resto do painel (ex.: o jogo sai da fila "Sem preço digital" do Revisar)
        <Digital jogo={jogo} aoAtualizar={(novo) => { aoAtualizar(novo); recarregar() }} aoCorrigir={aoCorrigir} />
      )}

      {jogo.historico.length > 1 && <Grafico ofertas={jogo.historico} mediana={jogo.mediana} />}

      <h3 className="ficha-titulo">
        Todas as ofertas <span className="titulo-num">{historico.length}</span>
      </h3>
      {marcadas.size > 0 && (
        <div className="barra-selecao" role="region" aria-label="Ofertas selecionadas">
          <span><strong>{marcadas.size}</strong> {marcadas.size === 1 ? 'selecionada' : 'selecionadas'}</span>
          <button className="botao destaque" onClick={() => setEditando(editando === 'varias' ? null : 'varias')}
            aria-expanded={editando === 'varias'}>
            Mover selecionadas
          </button>
          <button className="botao discreto" onClick={limparMarcadas}>Limpar seleção</button>
        </div>
      )}
      {editando === 'varias' && marcadas.size > 0 && (
        <MoverOferta ofertas={historico.filter((o) => marcadas.has(o.id))} jogo={jogo} plataformas={opcoes}
          aoMover={ofertaMovida} aoCancelar={() => setEditando(null)} />
      )}
      <table className="tabela">
        <thead>
          <tr>
            <th className="tabela-sel">
              <input type="checkbox" checked={todas} onChange={marcarTodas}
                ref={(el) => { if (el) el.indeterminate = marcadas.size > 0 && !todas }}
                aria-label="Selecionar todas as ofertas" />
            </th>
            <th>Data</th><th>Preço</th><th>Loja</th><th><span className="visualmente-oculto">Links</span></th>
          </tr>
        </thead>
        <tbody>
          {historico.map((o, indice) => {
            const ehMenor = o.preco === jogo.menor_preco
            const movendo = editando === o.id
            const marcada = marcadas.has(o.id)
            return (
              <Fragment key={o.id}>
              <tr className={[movendo && 'linha-ativa', marcada && 'linha-marcada', o.link_msg && o.link_msg === ultimo && 'linha-ultima'].filter(Boolean).join(' ') || undefined}>
                <td className="tabela-sel">
                  <input type="checkbox" checked={marcada} onChange={(e) => marcar(indice, e)}
                    aria-label={`Selecionar a oferta de ${brl(o.preco)} de ${dataTabela(o.data)}`} />
                </td>
                <td className="tabela-data">
                  {dataTabela(o.data)}
                  {o.link_msg === ultimo && <span id="ultimo-telegram" className="ultimo-aberto">último aberto</span>}
                </td>
                <td className="tabela-preco">
                  {ehMenor ? <mark className="marca-menor">{brl(o.preco)}</mark> : brl(o.preco)}
                </td>
                <td>
                  {o.loja || '—'}
                  {o.cupom && <Cupom codigo={o.cupom} />}
                  {!o.ativo && <span className="esgotou">esgotou</span>}
                </td>
                <td className="tabela-links">
                  {o.link && <a href={o.link} target="_blank" rel="noreferrer">Loja</a>}
                  {o.link_msg && (
                    <a href={o.link_msg} target="_blank" rel="noreferrer" className="link-telegram"
                      onClick={() => abriuTelegram(o.link_msg)} onAuxClick={() => abriuTelegram(o.link_msg)}
                      aria-describedby={o.link_msg === ultimo ? 'ultimo-telegram' : undefined}>
                      Telegram
                    </a>
                  )}
                  <button className="tabela-mover" onClick={() => setEditando(movendo ? null : o.id)}
                    aria-expanded={movendo} aria-label={`Mover a oferta de ${brl(o.preco)} para outro jogo ou console`}>
                    Mover
                  </button>
                </td>
              </tr>
              {movendo && (
                <tr className="linha-editor">
                  <td colSpan={5}>
                    <MoverOferta oferta={o} jogo={jogo} plataformas={opcoes}
                      aoMover={ofertaMovida} aoCancelar={() => setEditando(null)} />
                  </td>
                </tr>
              )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </>
  )
}

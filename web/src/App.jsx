import { useCallback, useEffect, useState } from 'react'
import { api, haQuanto } from './util'
import Jogos from './Jogos'
import Ofertas from './Ofertas'
import Desejos from './Desejos'
import Detalhe from './Detalhe'
import Revisao from './Revisao'
import Saude from './Saude'

const PLATAFORMAS_PADRAO = ['Switch 2', 'Switch', 'PS5', 'PS4']
const FILTRO_TIPOS = [['jogo', 'Jogos'], ['bundle', 'Bundles'], ['colecionador', 'Colecionador'], ['acessorio', 'Acessórios'], ['', 'Tudo']]
const ABAS = [['jogos', 'Jogos'], ['ofertas', 'Ofertas'], ['desejos', 'Lista de desejos'], ['revisao', 'Revisar'], ['saude', 'Saúde']]
const MARCAS = [['tenho', 'Já tenho'], ['ignorar', 'Não me interessa']]

export default function App() {
  const [aba, setAba] = useState('jogos')
  const [busca, setBusca] = useState('')
  const [plataforma, setPlataforma] = useState('')
  const [tipo, setTipo] = useState('jogo')   // a lista começa só com jogos
  const [marca, setMarca] = useState('')     // '' = esconde os marcados; 'tenho'/'ignorar' = só eles
  const [resumo, setResumo] = useState(null)
  const [erro, setErro] = useState('')
  const [versao, setVersao] = useState(0)
  const [aberto, setAberto] = useState(null) // id do jogo no painel lateral

  const carregarResumo = useCallback(() => {
    api('/resumo').then((r) => { setResumo(r); setErro('') })
      .catch(() => setErro('O monitor não está respondendo. Confira a janela do servidor e recarregue a página.'))
  }, [])

  useEffect(() => {
    carregarResumo()
    const t = setInterval(() => { carregarResumo(); setVersao((v) => v + 1) }, 60000)
    return () => clearInterval(t)
  }, [carregarResumo])

  // no celular a barra de abas rola para o lado: a aba escolhida (ex.: Saúde) fica sempre à vista
  useEffect(() => {
    document.querySelector('.aba.ativa')?.scrollIntoView({ inline: 'nearest', block: 'nearest' })
  }, [aba])

  const plataformas = resumo?.plataformas?.length ? resumo.plataformas : PLATAFORMAS_PADRAO

  const buscar = (texto) => {
    setBusca(texto)
    if (texto && aba !== 'jogos') setAba('jogos')
  }

  return (
    <div className="app">
      <header className="topo">
        <p className="marca">
          <span className="marca-selo" aria-hidden="true">R$</span>
          Monitor de jogos
        </p>
        {resumo && (
          <p className="status">
            {resumo.ofertas.toLocaleString('pt-BR')} ofertas de {resumo.jogos} jogos
            {resumo.ultima && <>, a última {haQuanto(resumo.ultima)}</>}
            {resumo.saude && (
              <button className={resumo.saude.ok ? 'status-saude ok' : 'status-saude ruim'} onClick={() => setAba('saude')}>
                {!resumo.saude.monitor ? 'Monitor parado' : resumo.saude.canais_parados
                  ? `${resumo.saude.canais_parados} ${resumo.saude.canais_parados === 1 ? 'canal parado' : 'canais parados'}`
                  : 'Monitor ligado'}
              </button>
            )}
          </p>
        )}
      </header>

      <section className={aba === 'jogos' ? 'busca' : 'busca compacta'} aria-label="Buscar preços">
        <h1 className={aba === 'jogos' ? 'busca-titulo' : 'visualmente-oculto'}>
          <label htmlFor="busca">Quanto está o jogo que você quer?</label>
        </h1>
        <div className="busca-campo">
          <svg aria-hidden="true" viewBox="0 0 24 24" width="22" height="22">
            <circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" strokeWidth="2.2" />
            <path d="M15.5 15.5 21 21" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
          </svg>
          <input id="busca" type="search" placeholder="Ex.: zelda, elden ring" value={busca}
            onChange={(e) => buscar(e.target.value)} autoComplete="off" spellCheck="false" />
          {busca && (
            <button className="busca-limpar" onClick={() => buscar('')} aria-label="Limpar busca">
              <svg aria-hidden="true" viewBox="0 0 16 16" width="14" height="14">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
          )}
        </div>
      </section>

      {erro && <p className="aviso-erro" role="alert">{erro}</p>}

      <div className="barra">
        <nav className="abas" role="tablist" aria-label="Seções">
          {ABAS.map(([id, nome]) => (
            <button key={id} role="tab" aria-selected={aba === id}
              className={aba === id ? 'aba ativa' : 'aba'} onClick={() => setAba(id)}>
              {nome}
              {id === 'desejos' && resumo?.desejos > 0 && <span className="aba-num">{resumo.desejos}</span>}
              {id === 'revisao' && resumo?.revisao > 0 && <span className="aba-num">{resumo.revisao}</span>}
              {id === 'saude' && resumo?.saude && !resumo.saude.ok && <span className="aba-alerta" aria-label="(com problema)">!</span>}
            </button>
          ))}
        </nav>
        {(aba === 'jogos' || aba === 'ofertas') && (
          <div className="filtros">
            <div className="plataformas" role="radiogroup" aria-label="Tipo">
              {FILTRO_TIPOS.map(([id, nome]) => (
                <button key={id || 'tudo'} role="radio" aria-checked={tipo === id}
                  className={tipo === id ? 'chip ativo' : 'chip'} onClick={() => setTipo(id)}>
                  {nome}
                  {id && id !== 'jogo' && resumo?.tipos?.[id] > 0 && <span className="chip-num">{resumo.tipos[id]}</span>}
                </button>
              ))}
            </div>
            <div className="plataformas" role="radiogroup" aria-label="Plataforma">
              {['', ...plataformas].map((p) => (
                <button key={p || 'todas'} role="radio" aria-checked={plataforma === p}
                  className={plataforma === p ? 'chip ativo' : 'chip'} onClick={() => setPlataforma(p)}>
                  {p || 'Todas'}
                </button>
              ))}
              <button role="radio" aria-checked={plataforma === 'sem'}
                className={plataforma === 'sem' ? 'chip ativo' : 'chip'} onClick={() => setPlataforma('sem')}>
                Sem plataforma
                {resumo?.sem_plataforma > 0 && <span className="chip-num">{resumo.sem_plataforma}</span>}
              </button>
            </div>
            {(marca || MARCAS.some(([id]) => resumo?.marcas?.[id] > 0)) && (
              <div className="plataformas marcas" role="group" aria-label="Escondidos da lista">
                {MARCAS.map(([id, nome]) => (
                  <button key={id} aria-pressed={marca === id} className={marca === id ? 'chip ativo' : 'chip'}
                    onClick={() => setMarca(marca === id ? '' : id)}>
                    {nome}
                    {resumo?.marcas?.[id] > 0 && <span className="chip-num">{resumo.marcas[id]}</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <main>
        {aba === 'jogos' && <Jogos busca={busca} plataforma={plataforma} tipo={tipo} marca={marca} versao={versao} abrir={setAberto} />}
        {aba === 'ofertas' && <Ofertas plataforma={plataforma} tipo={tipo} marca={marca} versao={versao} abrir={setAberto} />}
        {aba === 'desejos' && <Desejos versao={versao} aoMudar={carregarResumo} abrir={setAberto} />}
        {aba === 'revisao' && <Revisao versao={versao} abrir={setAberto} aoMudar={() => { carregarResumo(); setVersao((v) => v + 1) }} />}
        {aba === 'saude' && <Saude versao={versao} />}
      </main>

      {aberto && (
        <Detalhe id={aberto} versao={versao} aoFechar={() => setAberto(null)} abrir={setAberto}
          plataformas={resumo?.plataformas_validas}
          aoMudar={() => { carregarResumo(); setVersao((v) => v + 1) }} />
      )}
    </div>
  )
}

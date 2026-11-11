import { useEffect, useRef, useState } from 'react'
import { api, brl, TIPOS } from './util'
import Capa, { Plataforma } from './Capa'

/** Correção do jogo: nome e console. Se já existir o mesmo jogo no outro console, o servidor junta os dois. */
export function EditarJogo({ jogo, plataformas, aoSalvar, aoCancelar }) {
  const [nome, setNome] = useState(jogo.nome)
  const [plataforma, setPlataforma] = useState(jogo.plataforma || '')
  const [tipo, setTipo] = useState(jogo.tipo || 'jogo')
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState('')

  const salvar = async (e) => {
    e.preventDefault()
    setOcupado(true); setErro('')
    try {
      aoSalvar(await api(`/jogos/${jogo.id}/editar`, { method: 'POST', body: { nome, plataforma, tipo } }))
    } catch (err) { setErro(err.message); setOcupado(false) }
  }

  return (
    <form className="editor" onSubmit={salvar} aria-label="Corrigir jogo">
      <h3 className="editor-titulo">Corrigir</h3>
      <label className="campo">
        <span>Nome</span>
        <input value={nome} onChange={(e) => setNome(e.target.value)} required maxLength={200} />
      </label>
      <fieldset className="editor-grupo">
        <legend>Tipo</legend>
        <div className="plataformas" role="radiogroup">
          {TIPOS.map(([id, rotulo]) => (
            <button key={id} type="button" role="radio" aria-checked={tipo === id}
              className={tipo === id ? 'chip ativo' : 'chip'} onClick={() => setTipo(id)}>
              {rotulo}
            </button>
          ))}
        </div>
      </fieldset>
      {tipo !== 'jogo' && (
        <p className="editor-nota">
          {tipo === 'acessorio'
            ? 'Acessórios saem da lista de jogos (ficam no filtro “Acessórios”), não buscam preço digital e só alertam se estiverem na lista de desejos.'
            : tipo === 'bundle'
              ? 'Bundles saem da lista de jogos (ficam no filtro “Bundles”) e não buscam preço digital, mas continuam alertando preço bom.'
              : 'Edições de colecionador saem da lista de jogos (ficam no filtro “Colecionador”) e não buscam preço digital, mas continuam alertando preço bom.'}
        </p>
      )}
      <fieldset className="editor-grupo">
        <legend>Console</legend>
        <EscolhaPlataforma valor={plataforma} opcoes={plataformas} aoEscolher={setPlataforma} />
      </fieldset>
      <p className="editor-nota">
        Muda todas as {jogo.ofertas} ofertas deste jogo. Se só uma oferta está no console errado, use “Mover” na
        tabela de ofertas. Se o jogo já existir no console escolhido, os dois viram um só.
      </p>
      {erro && <p className="aviso-erro" role="alert">{erro}</p>}
      <div className="editor-acoes">
        <button className="botao" type="submit" disabled={ocupado}>{ocupado ? 'Salvando…' : 'Salvar'}</button>
        <button className="botao discreto" type="button" onClick={aoCancelar}>Cancelar</button>
      </div>
    </form>
  )
}

function EscolhaPlataforma({ valor, opcoes, aoEscolher, desabilitar }) {
  return (
    <div className="plataformas" role="radiogroup">
      {opcoes.map((p) => (
        <button key={p} type="button" role="radio" aria-checked={valor === p} disabled={desabilitar === p}
          className={valor === p ? 'chip ativo' : 'chip'} onClick={() => aoEscolher(p)}>
          {p}
        </button>
      ))}
    </div>
  )
}

/** Leva uma oferta para o mesmo jogo em outro console, ou para outro jogo da lista. */
/** Leva uma ou várias ofertas (do mesmo jogo) para o mesmo jogo em outro console, ou para outro jogo. */
export function MoverOferta({ oferta, ofertas, jogo, plataformas, aoMover, aoCancelar }) {
  const lista = ofertas || [oferta]
  const [busca, setBusca] = useState('')
  const [achados, setAchados] = useState([])
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    if (busca.trim().length < 2) { setAchados([]); return }
    const t = setTimeout(() => {
      api(`/jogos?${new URLSearchParams({ q: busca })}`)
        .then((r) => setAchados(r.filter((j) => j.id !== jogo.id).slice(0, 8)))
        .catch(() => setAchados([]))
    }, 200)
    return () => clearTimeout(t)
  }, [busca, jogo.id])

  const mover = async (corpo) => {
    setOcupado(true); setErro('')
    try {
      aoMover(await api('/ofertas/mover', { method: 'POST', body: { ...corpo, ids: lista.map((o) => o.id) } }))
    } catch (err) { setErro(err.message); setOcupado(false) }
  }

  return (
    <div className="editor editor-oferta" role="group"
      aria-label={lista.length === 1 ? `Mover a oferta de ${brl(lista[0].preco)}` : `Mover ${lista.length} ofertas`}>
      <p className="editor-nota">
        {lista.length === 1
          ? <>Oferta de <strong>{brl(lista[0].preco)}</strong> na {lista[0].loja || 'loja não informada'}. Ela é de qual jogo?</>
          : <><strong>{lista.length} ofertas</strong> selecionadas
            ({brl(Math.min(...lista.map((o) => o.preco)))} a {brl(Math.max(...lista.map((o) => o.preco)))}).
            Elas são de qual jogo?</>}
      </p>
      <div className="editor-grupo">
        <span className="editor-rotulo">Este mesmo jogo, mas em</span>
        <EscolhaPlataforma valor={null} opcoes={plataformas} desabilitar={jogo.plataforma}
          aoEscolher={(p) => !ocupado && mover({ plataforma: p })} />
      </div>
      <label className="campo">
        <span>Ou outro jogo</span>
        <input type="search" value={busca} onChange={(e) => setBusca(e.target.value)}
          placeholder="Digite o nome do jogo certo" autoComplete="off" />
      </label>
      {achados.length > 0 && (
        <ul className="editor-lista">
          {achados.map((j) => (
            <li key={j.id}>
              <button type="button" disabled={ocupado} onClick={() => mover({ jogo_id: j.id })}>
                <Capa src={j.capa} nome={j.nome} plataforma={j.plataforma} className="mini" />
                <span className="editor-lista-nome">{j.nome}</span>
                <Plataforma nome={j.plataforma} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {busca.trim().length >= 2 && achados.length === 0 && (
        <p className="editor-nota">Nenhum outro jogo com esse nome no monitor.</p>
      )}
      {erro && <p className="aviso-erro" role="alert">{erro}</p>}
      <div className="editor-acoes">
        <button className="botao discreto" type="button" onClick={aoCancelar}>Cancelar</button>
      </div>
    </div>
  )
}

const RECORTES_PRONTOS = [
  ['Metade esquerda', { x: 0, y: 0, w: 0.5, h: 1 }],
  ['Metade direita', { x: 0.5, y: 0, w: 0.5, h: 1 }],
  ['Metade de cima', { x: 0, y: 0, w: 1, h: 0.5 }],
  ['Metade de baixo', { x: 0, y: 0.5, w: 1, h: 0.5 }],
]
const MAX_ARQUIVO = 12 * 1024 * 1024

/** Trocar a capa: recortar a foto atual (bundles, duas versões), enviar outra imagem ou voltar à original. */
export function EditarCapa({ jogo, aoSalvar, aoCancelar }) {
  const [sel, setSel] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState('')
  const arquivo = useRef(null)

  const enviar = async (corpo) => {
    setOcupado(true); setErro('')
    try {
      aoSalvar(await api(`/jogos/${jogo.id}/capa`, { method: 'POST', body: corpo }))
      setSel(null)
    } catch (err) { setErro(err.message) }
    setOcupado(false)
  }

  const usarArquivo = (f) => {
    if (!f) return
    if (!f.type.startsWith('image/')) return setErro('Escolha um arquivo de imagem (JPG, PNG ou WEBP).')
    if (f.size > MAX_ARQUIVO) return setErro('Imagem grande demais (máximo 12 MB).')
    const leitor = new FileReader()
    leitor.onload = () => enviar({ imagem: leitor.result })
    leitor.readAsDataURL(f)
  }

  // Ctrl+V com uma imagem copiada (ex.: "Copiar imagem" no navegador) também troca a capa
  useEffect(() => {
    const colar = (e) => {
      const f = [...(e.clipboardData?.files || [])].find((x) => x.type.startsWith('image/'))
      if (f) { e.preventDefault(); usarArquivo(f) }
    }
    document.addEventListener('paste', colar)
    return () => document.removeEventListener('paste', colar)
  })

  return (
    <section className="editor" aria-label="Trocar a capa">
      <h3 className="editor-titulo">Trocar a capa</h3>
      {jogo.capa ? (
        <>
          <p className="editor-nota">
            Arraste sobre a foto para escolher a parte que fica (bom para bundles ou fotos com duas versões),
            ou use um dos recortes prontos. Depois ajuste puxando os cantos e as laterais, ou arraste a área para movê-la.
          </p>
          <Recorte src={jogo.capa} nome={jogo.nome} sel={sel} aoSelecionar={setSel} />
          <div className="plataformas">
            {RECORTES_PRONTOS.map(([rotulo, r]) => (
              <button key={rotulo} type="button" className="chip" onClick={() => setSel(r)}>{rotulo}</button>
            ))}
          </div>
        </>
      ) : (
        <p className="editor-nota">Este jogo ainda não tem capa. Envie uma imagem.</p>
      )}
      <p className="editor-nota">
        Também dá para <strong>colar uma imagem</strong> (Ctrl+V) copiada de um site.
      </p>
      {erro && <p className="aviso-erro" role="alert">{erro}</p>}
      <div className="editor-acoes">
        {jogo.capa && (
          <button className="botao destaque" type="button" disabled={!sel || ocupado} onClick={() => enviar({ recorte: sel })}>
            {ocupado ? 'Salvando…' : 'Recortar'}
          </button>
        )}
        <button className="botao secundario" type="button" disabled={ocupado} onClick={() => arquivo.current.click()}>
          Enviar outra imagem
        </button>
        <input ref={arquivo} type="file" accept="image/*" hidden
          onChange={(e) => { usarArquivo(e.target.files[0]); e.target.value = '' }} />
        {jogo.capa && !sel && <span className="editor-dica">Selecione uma área na foto para recortar</span>}
        {jogo.capa_original && (
          <button className="botao discreto" type="button" disabled={ocupado} onClick={() => enviar({ restaurar: true })}>
            Voltar à foto original
          </button>
        )}
        <button className="botao discreto" type="button" onClick={aoCancelar}>Fechar</button>
      </div>
    </section>
  )
}

const limite = (v, min = 0, max = 1) => Math.min(Math.max(v, min), max)
const MINIMO = 0.05                                   // menor recorte: 5% da foto em cada lado
// alças: quais bordas cada uma mexe (l = esquerda, r = direita, t = topo, b = base)
const ALCAS = [
  ['nw', 'lt'], ['n', 't'], ['ne', 'rt'], ['e', 'r'], ['se', 'rb'], ['s', 'b'], ['sw', 'lb'], ['w', 'l'],
]

/**
 * Seleção da área da capa. Arrastar na foto cria uma área nova; arrastar dentro dela move;
 * as alças dos cantos e laterais aumentam ou diminuem sem refazer.
 */
function Recorte({ src, nome, sel, aoSelecionar }) {
  const caixa = useRef(null)
  const img = useRef(null)
  const acao = useRef(null)   // { tipo: 'nova' | 'mover' | 'alca', bordas, inicio, original }

  const ponto = (e) => {
    const r = img.current.getBoundingClientRect()
    return { x: limite((e.clientX - r.left) / r.width), y: limite((e.clientY - r.top) / r.height) }
  }
  const pct = (v) => `${v * 100}%`

  const comecar = (e, tipo, bordas = '') => {
    if (e.button !== undefined && e.button !== 0) return
    e.preventDefault()
    e.stopPropagation()
    caixa.current.setPointerCapture(e.pointerId)
    acao.current = { tipo, bordas, inicio: ponto(e), original: sel }
  }

  const arrastar = (e) => {
    const a = acao.current
    if (!a) return
    const p = ponto(e)
    if (a.tipo === 'nova') {
      const r = { x: Math.min(a.inicio.x, p.x), y: Math.min(a.inicio.y, p.y),
        w: Math.abs(a.inicio.x - p.x), h: Math.abs(a.inicio.y - p.y) }
      if (r.w > 0.02 && r.h > 0.02) aoSelecionar(r)
      return
    }
    const o = a.original
    if (a.tipo === 'mover') {
      aoSelecionar({ ...o, x: limite(o.x + p.x - a.inicio.x, 0, 1 - o.w), y: limite(o.y + p.y - a.inicio.y, 0, 1 - o.h) })
      return
    }
    let l = o.x, r = o.x + o.w, t = o.y, b = o.y + o.h
    if (a.bordas.includes('l')) l = limite(p.x, 0, r - MINIMO)
    if (a.bordas.includes('r')) r = limite(p.x, l + MINIMO, 1)
    if (a.bordas.includes('t')) t = limite(p.y, 0, b - MINIMO)
    if (a.bordas.includes('b')) b = limite(p.y, t + MINIMO, 1)
    aoSelecionar({ x: l, y: t, w: r - l, h: b - t })
  }

  return (
    <div ref={caixa} className="recorte"
      onPointerDown={(e) => comecar(e, 'nova')}
      onPointerMove={arrastar}
      onPointerUp={() => { acao.current = null }}
      onPointerCancel={() => { acao.current = null }}>
      <img ref={img} src={src} alt={`Capa atual de ${nome}`} draggable="false" />
      {sel && (
        // o escurecimento fica numa camada recortada no tamanho da foto (senão cobria a gaveta toda);
        // a seleção e as alças ficam por cima, sem recorte, para as alças das bordas não sumirem
        <div className="recorte-mascara" aria-hidden="true">
          <div className="recorte-sombra" style={{ left: pct(sel.x), top: pct(sel.y), width: pct(sel.w), height: pct(sel.h) }} />
        </div>
      )}
      {sel && (
        <div className="recorte-sel" style={{ left: pct(sel.x), top: pct(sel.y), width: pct(sel.w), height: pct(sel.h) }}
          onPointerDown={(e) => comecar(e, 'mover')} title="Arraste para mover">
          {ALCAS.map(([pos, bordas]) => (
            <span key={pos} className={`recorte-alca ${pos}`} onPointerDown={(e) => comecar(e, 'alca', bordas)}
              aria-hidden="true" />
          ))}
        </div>
      )}
    </div>
  )
}

/** Exclusão do jogo e de todas as ofertas dele. Sempre pede confirmação. */
export function ExcluirJogo({ jogo, aoExcluir, aoCancelar }) {
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState('')
  const cancelar = useRef(null)
  useEffect(() => { cancelar.current?.focus() }, [])

  const excluir = async () => {
    setOcupado(true); setErro('')
    try {
      await api(`/jogos/${jogo.id}`, { method: 'DELETE', body: { confirmar: true } })
      aoExcluir()
    } catch (err) { setErro(err.message); setOcupado(false) }
  }
  const ofertas = jogo.ofertas === 1 ? 'a oferta' : `as ${jogo.ofertas} ofertas`

  return (
    <section className="editor editor-perigo" role="alertdialog" aria-labelledby="excluir-titulo" aria-describedby="excluir-texto">
      <h3 id="excluir-titulo" className="editor-titulo">Excluir “{jogo.nome}” ({jogo.plataforma || 'sem console'})?</h3>
      <p id="excluir-texto" className="editor-nota">
        O jogo e {ofertas} dele saem do monitor de vez, junto com a capa e o preço digital. <strong>Não dá para desfazer.</strong>
        {' '}Se só uma oferta está errada, use “Mover” na tabela em vez de excluir. Ofertas novas que chegarem depois
        voltam a aparecer normalmente.
      </p>
      {erro && <p className="aviso-erro" role="alert">{erro}</p>}
      <div className="editor-acoes">
        <button className="botao perigo" type="button" onClick={excluir} disabled={ocupado}>
          {ocupado ? 'Excluindo…' : `Excluir jogo e ${jogo.ofertas === 1 ? '1 oferta' : `${jogo.ofertas} ofertas`}`}
        </button>
        <button ref={cancelar} className="botao secundario" type="button" onClick={aoCancelar}>Cancelar</button>
      </div>
    </section>
  )
}


/** Imagem copiada (Ctrl+C / "Copiar imagem") como data URL, ou null. */
export function imagemDoEventoColar(e) {
  const f = [...(e.clipboardData?.files || [])].find((x) => x.type.startsWith('image/'))
  return f ? lerComoDataUrl(f) : null
}

/** Botão "Colar capa": lê a área de transferência. Só funciona em localhost ou HTTPS (regra do navegador). */
export async function imagemDaAreaDeTransferencia() {
  if (!navigator.clipboard?.read) {
    throw new Error('Este navegador não deixa ler a área de transferência por botão aqui. Com o jogo aberto, aperte Ctrl+V.')
  }
  let itens
  try {
    itens = await navigator.clipboard.read()
  } catch {
    throw new Error('O navegador não deixou ler a área de transferência. Com o jogo aberto, aperte Ctrl+V.')
  }
  for (const item of itens) {
    const tipo = item.types.find((t) => t.startsWith('image/'))
    if (tipo) return lerComoDataUrl(await item.getType(tipo))
  }
  throw new Error('Não há imagem copiada. Copie a imagem (botão direito → "Copiar imagem") e tente de novo.')
}

function lerComoDataUrl(arquivo) {
  if (arquivo.size > MAX_ARQUIVO) return Promise.reject(new Error('Imagem grande demais (máximo 12 MB).'))
  return new Promise((ok, falha) => {
    const leitor = new FileReader()
    leitor.onload = () => ok(leitor.result)
    leitor.onerror = () => falha(new Error('Não consegui ler a imagem.'))
    leitor.readAsDataURL(arquivo)
  })
}

/** Prévia da imagem colada: "Usar como capa?" */
export function ConfirmarCapa({ jogo, imagem, aoSalvar, aoCancelar }) {
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState('')
  const usar = useRef(null)
  useEffect(() => { usar.current?.focus() }, [])

  const salvar = async () => {
    setOcupado(true); setErro('')
    try {
      aoSalvar(await api(`/jogos/${jogo.id}/capa`, { method: 'POST', body: { imagem } }))
    } catch (err) { setErro(err.message); setOcupado(false) }
  }

  return (
    <section className="editor colar-capa" role="dialog" aria-labelledby="colar-capa-titulo">
      <h3 id="colar-capa-titulo" className="editor-titulo">Usar esta imagem como capa?</h3>
      <div className="colar-capa-previa">
        <img src={imagem} alt="Imagem colada" />
        {jogo.capa && <img src={jogo.capa} alt="Capa atual" className="colar-capa-atual" />}
      </div>
      <p className="editor-nota">
        À esquerda, a imagem colada{jogo.capa ? '; à direita, a capa de agora' : ''}. Depois dá para recortar em
        “Trocar capa”, ou voltar à foto original.
      </p>
      {erro && <p className="aviso-erro" role="alert">{erro}</p>}
      <div className="editor-acoes">
        <button ref={usar} className="botao destaque" type="button" onClick={salvar} disabled={ocupado}>
          {ocupado ? 'Salvando…' : 'Usar como capa'}
        </button>
        <button className="botao discreto" type="button" onClick={aoCancelar}>Cancelar</button>
      </div>
    </section>
  )
}

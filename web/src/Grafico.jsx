import { useEffect, useMemo, useRef, useState } from 'react'
import { brl, dataCompleta, dataCurta } from './util'

const ALT = 220
const M = { topo: 16, dir: 74, base: 28, esq: 56 }
const DIA = 864e5
const POUCOS_PONTOS = 40          // acima disso, sem bolinhas: só a linha

function ticksBonitos(min, max, n = 4) {
  const passoBruto = (max - min) / n || 10
  const mag = 10 ** Math.floor(Math.log10(passoBruto))
  const passo = [1, 2, 2.5, 5, 10].map((f) => f * mag).find((p) => p >= passoBruto)
  const ini = Math.floor(min / passo) * passo
  const out = []
  for (let v = ini; out.length < 2 || out[out.length - 1] < max; v += passo) out.push(v)
  return out
}

/** Início do dia ou da semana (segunda-feira) da data, no horário local. */
function inicio(t, porSemana) {
  const d = new Date(t)
  d.setHours(0, 0, 0, 0)
  if (porSemana) d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return d.getTime()
}

/**
 * Histórico de preços. Com várias lojas no mesmo dia, ligar oferta por oferta virava um serrote;
 * aqui cada dia (histórico curto) ou semana vira um ponto: a linha é o MENOR preço do período e a
 * faixa clara vai do mais barato ao mais caro.
 */
export default function Grafico({ ofertas, mediana }) {
  const caixa = useRef(null)
  const [larg, setLarg] = useState(600)
  const [foco, setFoco] = useState(null)

  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setLarg(Math.max(280, e.contentRect.width)))
    ro.observe(caixa.current)
    return () => ro.disconnect()
  }, [])

  const g = useMemo(() => {
    const pts = ofertas.map((o) => ({ ...o, t: new Date(o.data).getTime() }))
    const porSemana = (pts[pts.length - 1].t - pts[0].t) / DIA > 45
    const mapa = new Map()
    for (const p of pts) {
      const k = inicio(p.t, porSemana)
      const b = mapa.get(k) || { t: k, min: Infinity, max: -Infinity, n: 0, melhor: null }
      b.n += 1
      b.max = Math.max(b.max, p.preco)
      if (p.preco < b.min) { b.min = p.preco; b.melhor = p }
      mapa.set(k, b)
    }
    const grupos = [...mapa.values()].sort((a, b) => a.t - b.t)

    const precos = pts.map((p) => p.preco)
    const ticks = ticksBonitos(Math.min(...precos) * 0.92, Math.max(...precos) * 1.05)
    const yMin = ticks[0], yMax = ticks[ticks.length - 1]
    const t0 = grupos[0].t, t1 = grupos[grupos.length - 1].t
    const w = larg - M.esq - M.dir, h = ALT - M.topo - M.base
    const x = (t) => M.esq + (t1 === t0 ? w / 2 : ((t - t0) / (t1 - t0)) * w)
    const y = (v) => M.topo + h - ((v - yMin) / (yMax - yMin)) * h
    const menorIdx = grupos.reduce((m, b, i) => (b.min < grupos[m].min ? i : m), 0)

    // rótulos do eixo x: início, meio e fim, sem repetir o mesmo dia
    const dia = (t) => dataCurta(new Date(t).toISOString())
    const xTicks = [t0, (t0 + t1) / 2, t1].filter((t, i, todos) => i === 0 || dia(t) !== dia(todos[i - 1]))
      .filter((t, i, todos) => i === 0 || dia(t) !== dia(todos[0]))
    if (xTicks.length === 1) xTicks[0] = (t0 + t1) / 2

    const linha = grupos.map((b, i) => `${i ? 'L' : 'M'}${x(b.t)},${y(b.min)}`).join(' ')
    const temFaixa = grupos.some((b) => b.max > b.min)
    const faixa = temFaixa
      ? `M${grupos.map((b) => `${x(b.t)},${y(b.max)}`).join(' L')} L${[...grupos].reverse().map((b) => `${x(b.t)},${y(b.min)}`).join(' L')} Z`
      : null
    return { grupos, porSemana, ticks, x, y, menorIdx, xTicks, w, h, linha, faixa }
  }, [ofertas, larg])

  const mover = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - r.left) / r.width) * larg
    let melhor = 0
    g.grupos.forEach((b, i) => {
      if (Math.abs(g.x(b.t) - px) < Math.abs(g.x(g.grupos[melhor].t) - px)) melhor = i
    })
    setFoco(melhor)
  }

  const ponto = foco != null ? g.grupos[foco] : null
  const menor = g.grupos[g.menorIdx]
  const yMed = g.y(mediana)
  const periodo = (b) => (g.porSemana ? `Semana de ${dataCurta(new Date(b.t).toISOString())}` : dataCompleta(new Date(b.t).toISOString()))

  return (
    <figure className="grafico" ref={caixa}>
      <figcaption className="ficha-titulo">Histórico de preços</figcaption>
      <div className="grafico-area">
      <svg
        viewBox={`0 0 ${larg} ${ALT}`} width="100%" height={ALT}
        role="img" aria-label={`Menor preço de cada ${g.porSemana ? 'semana' : 'dia'}. Menor de todos ${brl(menor.min)}, normal ${brl(mediana)}.`}
        onPointerMove={mover} onPointerLeave={() => setFoco(null)}
      >
        {g.ticks.map((v) => (
          <g key={v}>
            <line x1={M.esq} x2={larg - M.dir} y1={g.y(v)} y2={g.y(v)} className="g-grade" />
            <text x={M.esq - 8} y={g.y(v)} className="g-eixo" textAnchor="end" dominantBaseline="middle">
              {brl(v).replace(',00', '')}
            </text>
          </g>
        ))}
        {g.xTicks.map((t, i) => (
          <text key={i} x={g.x(t)} y={ALT - 8} className="g-eixo"
            textAnchor={g.xTicks.length === 1 ? 'middle' : i === 0 ? 'start' : i === g.xTicks.length - 1 ? 'end' : 'middle'}>
            {dataCurta(new Date(t).toISOString())}
          </text>
        ))}

        {g.faixa && <path d={g.faixa} className="g-faixa" />}

        <line x1={M.esq} x2={larg - M.dir} y1={yMed} y2={yMed} className="g-mediana" />
        <text x={larg - M.dir + 8} y={yMed} dominantBaseline="middle" className="g-mediana-rotulo">
          <tspan x={larg - M.dir + 8} dy="-0.55em">normal</tspan>
          <tspan x={larg - M.dir + 8} dy="1.15em">{brl(mediana).replace(',00', '')}</tspan>
        </text>

        <path d={g.linha} className="g-linha" />
        {g.grupos.length <= POUCOS_PONTOS && g.grupos.map((b, i) => (i === g.menorIdx ? null : (
          <circle key={b.t} cx={g.x(b.t)} cy={g.y(b.min)} r={3.5} className="g-ponto" />
        )))}
        <circle cx={g.x(menor.t)} cy={g.y(menor.min)} r={7} className="g-menor" />
        {!ponto && (() => {
          const mx = g.x(menor.t), aDireita = mx < larg * 0.6
          return (
            <text x={mx + (aDireita ? 12 : -12)} y={g.y(menor.min)} dominantBaseline="middle"
              textAnchor={aDireita ? 'start' : 'end'} className="g-menor-rotulo">
              menor {brl(menor.min)}
            </text>
          )
        })()}

        {ponto && (
          <g pointerEvents="none">
            <line x1={g.x(ponto.t)} x2={g.x(ponto.t)} y1={M.topo} y2={M.topo + g.h} className="g-cruz" />
            {ponto.max > ponto.min && (
              <line x1={g.x(ponto.t)} x2={g.x(ponto.t)} y1={g.y(ponto.max)} y2={g.y(ponto.min)} className="g-foco-faixa" />
            )}
            <circle cx={g.x(ponto.t)} cy={g.y(ponto.min)} r={6} className="g-foco" />
          </g>
        )}
      </svg>
      {ponto && (
        <div
          className="g-dica"
          style={{
            left: `${(g.x(ponto.t) / larg) * 100}%`,
            top: g.y(ponto.min) > ALT / 2 ? g.y(ponto.min) - 14 : g.y(ponto.min) + 14,
            transform: `translate(${g.x(ponto.t) > larg * 0.7 ? '-100%' : g.x(ponto.t) < larg * 0.3 ? '0' : '-50%'}, ${g.y(ponto.min) > ALT / 2 ? '-100%' : '0'})`,
          }}
        >
          <span>{periodo(ponto)}</span>
          <strong>{brl(ponto.min)}</strong>
          <span>{ponto.melhor.loja || 'Loja não informada'}</span>
          {ponto.n > 1 && <span>{ponto.n} ofertas, até {brl(ponto.max)}</span>}
        </div>
      )}
      </div>
      <p className="g-legenda">
        <span className="g-legenda-linha" aria-hidden="true" /> menor preço de cada {g.porSemana ? 'semana' : 'dia'}
        {g.faixa && <><span className="g-legenda-faixa" aria-hidden="true" /> do mais barato ao mais caro</>}
        <span className="g-legenda-mediana" aria-hidden="true" /> preço normal
      </p>
    </figure>
  )
}

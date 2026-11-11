import { useEffect, useState } from 'react'
import { api, dataCompleta, haQuanto } from './util'

const mb = (b) => `${((b || 0) / 1024 / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`
const hora = (iso) => new Date(iso).toLocaleString('pt-BR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).replace('.', '')

function Sinal({ ok, sim, nao }) {
  return <span className={ok ? 'sinal ok' : 'sinal ruim'}>{ok ? sim : nao}</span>
}

/** Está tudo funcionando? Monitor, canais, Deku Deals, espaço em disco e últimos erros. */
export default function Saude({ versao }) {
  const [s, setS] = useState(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    api('/saude').then((r) => { setS(r); setErro('') }).catch((e) => setErro(e.message))
  }, [versao])

  if (erro) return <p className="aviso-erro" role="alert">{erro}</p>
  if (!s) return <p className="vazio">Carregando…</p>
  const m = s.monitor
  const d = s.digital || {}
  const e = s.espaco
  const totalBackups = e.backups.reduce((t, b) => t + b.bytes, 0)

  return (
    <div className="saude">
      <div className="secao-topo">
        <h2 className="secao-titulo">Saúde do monitor</h2>
        <p className="secao-nota">Atualiza sozinha a cada minuto. Canal parado também gera um aviso no seu Telegram.</p>
      </div>

      <div className="saude-grade">
        <section className="saude-cartao" aria-labelledby="sd-monitor">
          <h3 id="sd-monitor" className="saude-titulo">Monitor</h3>
          <p><Sinal ok={m.ativo} sim="Ligado" nao="Parado" /></p>
          <p className="saude-nota">
            {m.ultima_batida ? <>Último sinal {haQuanto(m.ultima_batida)}.</> : 'Ainda sem sinal desde a atualização.'}
            {!m.ativo && m.ultima_batida && <> Sem sinal há mais de {m.limite_min} min: o servidor pode ter caído.</>}
          </p>
          {m.ligado_desde && <p className="saude-nota">Ligado desde {hora(m.ligado_desde)}.</p>}
          {m.telegram_conectado != null && (
            <p className="saude-nota">Telegram: {m.telegram_conectado ? 'conectado' : 'desconectado (tentando reconectar)'}.</p>
          )}
        </section>

        <section className="saude-cartao" aria-labelledby="sd-digital">
          <h3 id="sd-digital" className="saude-titulo">Preços digitais (Deku Deals)</h3>
          <p className="saude-num">{(d.com_preco || 0).toLocaleString('pt-BR')} <span>de {(d.total || 0).toLocaleString('pt-BR')} jogos com preço</span></p>
          {d.ultimo && <p className="saude-nota">Última consulta {haQuanto(d.ultimo)}.</p>}
          {d.erros > 0 && <p className="saude-nota">{d.erros} sem página no Deku Deals ou com erro na última consulta.</p>}
        </section>

        <section className="saude-cartao" aria-labelledby="sd-espaco">
          <h3 id="sd-espaco" className="saude-titulo">Espaço</h3>
          <dl className="saude-lista">
            <div><dt>Banco</dt><dd>{mb(e.banco)}</dd></div>
            <div><dt>Capas</dt><dd>{mb(e.capas.bytes)} <span>({e.capas.arquivos.toLocaleString('pt-BR')} arquivos)</span></dd></div>
            <div><dt>Backups</dt><dd>{mb(totalBackups)} <span>({e.backups.length} de no máximo {e.backups_manter})</span></dd></div>
          </dl>
          <p className="saude-nota">
            Backup automático 1x por dia; ficam os {e.backups_manter} mais novos.
            {e.ultimo_backup ? <> Último {haQuanto(e.ultimo_backup)}.</> : ' O primeiro sai quando o monitor reiniciar.'}
          </p>
        </section>
      </div>

      <h3 className="ficha-titulo">Canais</h3>
      {s.silencio_geral.parado && (
        <p className="aviso-erro" role="alert">
          Nenhum canal mandou nada há mais de {s.silencio_geral.limite_horas} h. Confira a conexão do monitor com o Telegram.
        </p>
      )}
      <table className="tabela saude-canais">
        <thead>
          <tr><th>Canal</th><th>Última mensagem</th><th>Ofertas em 24 h</th><th>Situação</th></tr>
        </thead>
        <tbody>
          {s.canais.map((c) => (
            <tr key={c.id}>
              <td>{c.nome}</td>
              <td className="tabela-data">{c.ultima_mensagem ? haQuanto(c.ultima_mensagem) : '—'}</td>
              <td>{c.ofertas_24h}</td>
              <td>
                <Sinal ok={!c.parado} sim="Ok" nao={`Parado há mais de ${c.limite_horas} h`} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="ficha-titulo">Backups</h3>
      {e.backups.length === 0 ? <p className="vazio">Nenhum backup ainda.</p> : (
        <ul className="saude-backups">
          {e.backups.map((b) => (
            <li key={b.nome}><span>{b.nome}</span><span>{dataCompleta(b.data)}, {mb(b.bytes)}</span></li>
          ))}
        </ul>
      )}

      <h3 className="ficha-titulo">Últimos avisos e erros</h3>
      {s.erros.length === 0 ? <p className="vazio">Nenhum aviso registrado.</p> : (
        <ul className="saude-erros">
          {s.erros.map((x, i) => (
            <li key={i}>
              <span className={x.nivel === 'WARNING' ? 'sinal aviso' : 'sinal ruim'}>{x.nivel === 'WARNING' ? 'Aviso' : 'Erro'}</span>
              <span className="saude-erro-data">{hora(x.data)}</span>
              <code>{x.texto}</code>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

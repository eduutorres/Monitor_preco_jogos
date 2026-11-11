export const api = async (caminho, opcoes = {}) => {
  const r = await fetch(`api${caminho}`, {   // relativo ao <base href> da página
    headers: { 'Content-Type': 'application/json' },
    ...opcoes,
    body: opcoes.body ? JSON.stringify(opcoes.body) : undefined,
  })
  const dados = await r.json().catch(() => null)
  if (!r.ok) throw new Error(dados?.erro || 'Não foi possível falar com o monitor.')
  return dados
}

const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
export const brl = (v) => (v == null ? '—' : moeda.format(v))

export const dataCurta = (iso) =>
  new Date(iso).toLocaleDateString('pt-BR', { day: 'numeric', month: 'short' }).replace('.', '')

export const dataCompleta = (iso) =>
  new Date(iso).toLocaleDateString('pt-BR', { day: 'numeric', month: 'short', year: 'numeric' }).replace('.', '')

export function haQuanto(iso) {
  const min = (Date.now() - new Date(iso).getTime()) / 60000
  if (min < 1) return 'agora'
  if (min < 60) return `há ${Math.round(min)} min`
  const h = min / 60
  if (h < 24) return `há ${Math.round(h)} h`
  const d = Math.round(h / 24)
  if (d === 1) return 'ontem'
  if (d < 30) return `há ${d} dias`
  return dataCurta(iso)
}

export function rotuloDia(iso) {
  const d = new Date(iso)
  const hoje = new Date()
  const ontem = new Date(Date.now() - 864e5)
  if (d.toDateString() === hoje.toDateString()) return 'Hoje'
  if (d.toDateString() === ontem.toDateString()) return 'Ontem'
  return d.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' })
}

export function dataTabela(iso) {
  const d = new Date(iso)
  const mesmoAno = d.getFullYear() === new Date().getFullYear()
  const txt = d.toLocaleDateString('pt-BR', { day: 'numeric', month: 'short', ...(mesmoAno ? {} : { year: 'numeric' }) })
  return txt.replace(/\./g, '').replace(/ de /g, ' ')
}

// Último Telegram aberto de cada jogo (fica salvo neste navegador). { [jogoId]: link da mensagem }
const CHAVE_TELEGRAM = 'monitor.telegramPorJogo'
const lerMapa = () => { try { return JSON.parse(localStorage.getItem(CHAVE_TELEGRAM)) || {} } catch { return {} } }

export const ultimoTelegram = (jogoId) => lerMapa()[jogoId] || null

export function marcarTelegram(jogoId, link) {
  const mapa = lerMapa()
  delete mapa[jogoId]
  mapa[jogoId] = link                                   // o mais recente fica por último
  const ids = Object.keys(mapa)
  for (const id of ids.slice(0, Math.max(0, ids.length - 500))) delete mapa[id]   // não cresce sem fim
  try { localStorage.setItem(CHAVE_TELEGRAM, JSON.stringify(mapa)) } catch { /* modo privado */ }
}

// Tipo do item (definido à mão no painel)
export const TIPOS = [['jogo', 'Jogo'], ['bundle', 'Bundle'], ['colecionador', 'Colecionador'], ['acessorio', 'Acessório']]
export const nomeTipo = (t) => (TIPOS.find(([id]) => id === t) || TIPOS[0])[1]

// "Já tenho" / "Não me interessa": some das listas e não gera alerta (só a lista de desejos avisa)
export const nomeMarca = (m) => ({ tenho: 'Já tenho', ignorar: 'Não me interessa' })[m] || ''

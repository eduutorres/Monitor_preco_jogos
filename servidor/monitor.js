/*
 * Monitor de preços de jogos: módulo para plugar no SEU servidor Node.
 * Não tem dependências (não precisa de npm install).
 *
 *   Express:
 *     const monitor = require('C:/paineis/monitor_jogos/servidor/monitor.js')
 *     app.use('/monitorprecojogos', monitor.handler)
 *
 *   http puro:
 *     const monitor = require('C:/paineis/monitor_jogos/servidor/monitor.js')
 *     http.createServer((req, res) => {
 *       if (req.url.startsWith('/monitorprecojogos')) return monitor.handler(req, res)
 *       ...seus outros painéis...
 *     })
 *
 * Ao ser carregado, ele inicia o monitor Python escondido (127.0.0.1:portaPython) e o
 * reinicia se cair. O painel e as chamadas /api e /capas passam por aqui.
 */
'use strict'

const http = require('http')
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const { spawn, spawnSync } = require('child_process')

const RAIZ = path.resolve(__dirname, '..')            // pasta do monitor (config.py, banco; o código fica em codigo/)
const PAINEL = path.join(RAIZ, 'dist')
const NOME = '[monitorprecojogos]'

// ------------------------------------------------------------------ configuração
const PADRAO = {
  prefixo: '/monitorprecojogos',  // endereço dentro do seu servidor
  senha: '',                      // vazio = sem senha (use se o seu servidor não tiver login)
  python: '',                     // vazio = descobre sozinho (python ou py -3)
  portaPython: 8787,              // porta interna do monitor Python (só 127.0.0.1)
  pastaLogs: 'logs',
  demo: false,                    // true = dados de demonstração, sem Telegram
}

function lerConfig(extra = {}) {
  const arq = path.join(__dirname, 'config.json')
  let cfg = { ...PADRAO }
  if (fs.existsSync(arq)) {
    try {
      cfg = { ...cfg, ...JSON.parse(fs.readFileSync(arq, 'utf8')) }
    } catch (e) {
      throw new Error(`${NOME} O arquivo ${arq} tem um erro de digitação: ${e.message}`)
    }
  }
  cfg = { ...cfg, ...extra }
  cfg.prefixo = ('/' + String(cfg.prefixo || '').replace(/^\/+|\/+$/g, '')).replace(/^\/$/, '')
  return cfg
}

// ------------------------------------------------------------------ o monitor
function criarMonitor(opcoes = {}) {
  const cfg = lerConfig(opcoes)
  const pastaLogs = path.resolve(RAIZ, cfg.pastaLogs)
  fs.mkdirSync(pastaLogs, { recursive: true })
  const arqLog = path.join(pastaLogs, 'monitor.log')
  const arqPid = path.join(pastaLogs, 'monitor.pid')

  function log(linha) {
    const texto = `${new Date().toLocaleString('pt-BR')}  ${linha}`
    console.log(`${NOME} ${linha}`)
    try {
      if (fs.existsSync(arqLog) && fs.statSync(arqLog).size > 5 * 1024 * 1024) {
        fs.renameSync(arqLog, arqLog + '.1')
      }
      fs.appendFileSync(arqLog, texto + '\n')
    } catch { /* log em arquivo é opcional */ }
  }

  // ---------------------------------------------------------------- Python
  function acharPython() {
    const tentativas = cfg.python ? [[cfg.python]] : [['python'], ['py', '-3'], ['python3']]
    for (const [cmd, ...args] of tentativas) {
      const r = spawnSync(cmd, [...args, '--version'], { encoding: 'utf8', windowsHide: true })
      if (r.status === 0) return { cmd, args, versao: (r.stdout || r.stderr).trim() }
    }
    return null
  }

  function encerrarOrfao() {
    // se o seu servidor foi fechado à força, o Python da vez anterior pode ter ficado rodando
    try {
      const pid = Number(fs.readFileSync(arqPid, 'utf8'))
      if (pid && ehNossoPython(pid)) process.kill(pid)
    } catch { /* não havia nenhum */ }
  }

  function ehNossoPython(pid) {
    // o Windows reaproveita PIDs: só encerra se ainda for o monitor.py/api.py
    let linha = ''
    if (process.platform === 'win32') {
      const r = spawnSync('powershell', ['-NoProfile', '-Command',
        `(Get-CimInstance Win32_Process -Filter "ProcessId=${pid}").CommandLine`],
      { encoding: 'utf8', windowsHide: true })
      linha = r.stdout || ''
    } else {
      try { linha = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8') } catch { /* não existe */ }
    }
    return /python|py(\.exe)?\b/i.test(linha) && /(monitor|api)\.py/.test(linha)
  }

  const py = acharPython()
  let filho = null
  let parado = false
  let espera = 5
  let iniciouEm = 0
  let faltaLogin = false
  let faltaConfig = false

  function iniciarPython() {
    if (parado) return
    if (cfg.demo) {
      spawnSync(py.cmd, [...py.args, path.join('codigo', 'gerar_demo.py')], { cwd: RAIZ, stdio: 'ignore', windowsHide: true })
    }
    const script = cfg.demo ? [path.join('codigo', 'api.py'), '--demo', String(cfg.portaPython)] : [path.join('codigo', 'monitor.py')]
    iniciouEm = Date.now()
    faltaLogin = false
    faltaConfig = false
    filho = spawn(py.cmd, [...py.args, ...script], {
      cwd: RAIZ,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        HOST_PAINEL: '127.0.0.1',            // o Python só atende este computador
        PORTA_PAINEL: String(cfg.portaPython),
        SENHA_PAINEL: '',                    // a senha (se houver) é conferida aqui no Node
        PYTHONUNBUFFERED: '1',
        MONITOR_SEM_TERMINAL: '1',           // não há como digitar telefone/código aqui
        PYTHONUTF8: '1',                     // emojis no log sem erro no Windows
        PYTHONIOENCODING: 'utf-8',
      },
    })
    try { fs.writeFileSync(arqPid, String(filho.pid)) } catch { /* opcional */ }

    const repassarLog = (dados) => {
      for (const linha of dados.toString('utf8').split(/\r?\n/)) {
        if (!linha.trim()) continue
        log(linha)
        if (/ainda não fez login/i.test(linha)) faltaLogin = true
        if (/preencha o config\.py/i.test(linha)) faltaConfig = true
      }
    }
    filho.stdout.on('data', repassarLog)
    filho.stderr.on('data', repassarLog)
    filho.on('error', (e) => log(`Não consegui iniciar o Python: ${e.message}`))
    filho.on('exit', (codigo) => {
      filho = null
      try { fs.unlinkSync(arqPid) } catch { /* já não existe */ }
      if (parado) return
      const durou = (Date.now() - iniciouEm) / 1000
      espera = durou < 30 ? Math.min(espera * 2, 300) : 5
      if (faltaLogin) {
        log('⚠️  Falta fazer login no Telegram. Abra um Prompt de Comando na pasta do monitor e rode: '
          + 'python codigo\\listar_canais.py   (o monitor tenta de novo sozinho depois).')
        espera = Math.max(espera, 60)
      }
      if (faltaConfig) espera = 300               // só volta a funcionar depois que você editar o config.py
      log(`O monitor parou (código ${codigo}). Reiniciando em ${espera}s...`)
      setTimeout(iniciarPython, espera * 1000)
    })
  }

  // ---------------------------------------------------------------- senha
  function senhaConfere(req) {
    if (!cfg.senha) return true
    const cab = req.headers.authorization || ''
    if (!cab.startsWith('Basic ')) return false
    const texto = Buffer.from(cab.slice(6), 'base64').toString('utf8')
    const senha = texto.slice(texto.indexOf(':') + 1)
    const a = crypto.createHash('sha256').update(senha).digest()
    const b = crypto.createHash('sha256').update(cfg.senha).digest()
    return crypto.timingSafeEqual(a, b)
  }

  // ---------------------------------------------------------------- arquivos
  const TIPOS = {
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png',
    '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.json': 'application/json',
    '.woff2': 'font/woff2', '.woff': 'font/woff', '.txt': 'text/plain; charset=utf-8',
  }

  function servirArquivo(req, res, caminho, base) {
    let alvo = path.resolve(PAINEL, '.' + caminho)
    const dentro = alvo === PAINEL || alvo.startsWith(PAINEL + path.sep)
    if (!dentro || !fs.existsSync(alvo) || !fs.statSync(alvo).isFile()) {
      alvo = path.join(PAINEL, 'index.html')          // o painel cuida das próprias telas
    }
    if (!fs.existsSync(alvo)) {
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' })
      return res.end('A pasta "dist" (painel compilado) não foi encontrada ao lado da pasta "servidor".')
    }
    const tipo = TIPOS[path.extname(alvo).toLowerCase()] || 'application/octet-stream'
    if (path.basename(alvo) === 'index.html') {
      // o build usa caminhos relativos; o <base> diz em qual pasta o painel está
      const html = fs.readFileSync(alvo, 'utf8').replace('<head>', `<head><base href="${base}">`)
      res.writeHead(200, { 'Content-Type': tipo, 'Cache-Control': 'no-cache' })
      return res.end(req.method === 'HEAD' ? undefined : html)
    }
    const ehAsset = alvo.includes(path.sep + 'assets' + path.sep)
    res.writeHead(200, {
      'Content-Type': tipo,
      'Cache-Control': ehAsset ? 'public, max-age=31536000, immutable' : 'no-cache',
      'X-Content-Type-Options': 'nosniff',
    })
    if (req.method === 'HEAD') return res.end()
    fs.createReadStream(alvo).pipe(res)
  }

  // ---------------------------------------------------------------- repasse ao Python
  function repassar(req, res, caminho) {
    const headers = { ...req.headers }
    delete headers.authorization
    let corpo = null
    // se o seu servidor já leu o corpo (ex.: app.use(express.json())), reenvia o que ele leu
    if (req.body !== undefined && req.readableEnded) {
      corpo = Buffer.from(typeof req.body === 'string' ? req.body : JSON.stringify(req.body))
      headers['content-length'] = String(corpo.length)
      delete headers['transfer-encoding']
    }
    const pedido = http.request(
      { host: '127.0.0.1', port: cfg.portaPython, method: req.method, path: caminho, headers },
      (resposta) => {
        res.writeHead(resposta.statusCode, resposta.headers)
        resposta.pipe(res)
      },
    )
    pedido.on('error', () => {
      if (res.headersSent) return res.end()
      res.writeHead(503, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(JSON.stringify({
        erro: 'O monitor ainda está iniciando ou parou. Veja o log do servidor (ou logs/monitor.log).',
      }))
    })
    if (corpo) pedido.end(corpo)
    else req.pipe(pedido)
  }

  // ---------------------------------------------------------------- handler
  /** Funciona como middleware do Express (app.use) ou chamado direto num servidor http. */
  function handler(req, res, next) {
    try {
      // Express já tira o prefixo do req.url (e guarda em req.baseUrl); no http puro tiramos aqui
      let url = req.url || '/'
      const montadoEm = req.baseUrl !== undefined ? req.baseUrl : cfg.prefixo
      if (req.baseUrl === undefined && cfg.prefixo && url.startsWith(cfg.prefixo)) {
        url = url.slice(cfg.prefixo.length)
      }
      if (!url.startsWith('/')) url = '/' + url
      const base = (montadoEm || '') + '/'

      if (!senhaConfere(req)) {
        res.writeHead(401, {
          'WWW-Authenticate': 'Basic realm="Monitor de jogos", charset="UTF-8"',
          'Content-Type': 'text/plain; charset=utf-8',
        })
        return res.end('Senha necessária.')
      }
      if (url.startsWith('/api/') || url.startsWith('/capas/')) return repassar(req, res, url)
      if (req.method !== 'GET' && req.method !== 'HEAD') {
        if (next) return next()
        res.writeHead(405)
        return res.end()
      }
      let caminho
      try {
        caminho = decodeURIComponent(new URL(url, 'http://x').pathname)
      } catch {
        res.writeHead(400)
        return res.end()
      }
      servirArquivo(req, res, caminho, base)
    } catch (e) {
      log(`Erro ao responder ${req.method} ${req.url}: ${e.message}`)
      if (next) return next(e)
      if (!res.headersSent) res.writeHead(500)
      res.end()
    }
  }

  function parar() {
    parado = true
    if (filho) filho.kill()
  }

  // ---------------------------------------------------------------- início
  if (!py) {
    log('❌ Não encontrei o Python. Instale o Python 3.10+ (marque "Add python.exe to PATH") '
      + 'ou informe o caminho em "python" no servidor/config.json.')
  } else {
    log(`Python: ${py.versao}${cfg.demo ? '  (modo demonstração)' : ''}. Painel em ${cfg.prefixo || '/'}`)
    encerrarOrfao()
    iniciarPython()
  }
  process.once('exit', parar)                    // seu servidor fechou: fecha o Python junto

  return { handler, parar, config: cfg }
}

// ------------------------------------------------------------------ uso simples
// require('.../monitor.js').handler já inicia com o servidor/config.json.
// Para outras opções: require('.../monitor.js').criarMonitor({ prefixo: '/jogos', senha: 'x' })
let padrao = null
function obterPadrao() {
  if (!padrao) padrao = criarMonitor()
  return padrao
}

module.exports = {
  criarMonitor,
  get handler() { return obterPadrao().handler },
  parar: () => padrao && padrao.parar(),
}

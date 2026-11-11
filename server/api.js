/**
 * Ponte entre o host de C:\www e o monitor Python.
 *
 * O server.js de C:\www monta este módulo em /Monitor_preco_jogos/api e serve
 * o painel compilado (dist/) como os outros sites. Ao ser carregado, ele sobe o
 * monitor Python escondido em 127.0.0.1 (servidor/monitor.js cuida de reiniciar
 * se cair) e repassa as chamadas /api — inclusive as capas, em /api/capas.
 *
 * Ajustes (senha, caminho do Python, porta interna, modo demo): servidor/config.json
 */
'use strict';

const { criarMonitor } = require('../servidor/monitor.js');

// o host chama criarApi({ silencioso: true }); o resto (demo, portaPython...) sobrepõe o config.json
function criarApi({ silencioso, ...extra } = {}) {
  const monitor = criarMonitor(extra);

  return function api(req, res, next) {
    // o host já tirou o "/Monitor_preco_jogos/api" do caminho; o Python espera /api/...
    req.url = '/api' + (req.url.startsWith('/') ? req.url : '/' + req.url);
    monitor.handler(req, res, next);
  };
}

module.exports = criarApi;
module.exports.criarApi = criarApi;

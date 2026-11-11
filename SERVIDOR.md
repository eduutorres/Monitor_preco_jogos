# Rodando no servidor de C:\www

O monitor segue o mesmo padrão dos outros apps de `C:\www` (afetodenos, estante...).
O `server.js` de `C:\www` encontra esta pasta sozinho, sem nenhuma alteração nele:

```
navegador ──► C:\www\server.js
                ├─ /Monitor_preco_jogos/      → dist/ (painel compilado)
                └─ /Monitor_preco_jogos/api/  → server/api.js ──► monitor Python (127.0.0.1:8787)
```

- `dist/` — o painel React compilado. É a **única** coisa servida como arquivo; o `codigo/`,
  o `config.py`, o banco e as sessões do Telegram nunca ficam acessíveis pelo navegador.
- `server/api.js` — ao subir o servidor, inicia o monitor Python escondido (Telegram, preços,
  Deku Deals, alertas), reinicia se cair e repassa o `/api` (inclusive as capas, em `/api/capas`).
- `servidor/monitor.js` — quem de fato cuida do Python. `servidor/config.json` tem os ajustes.

O log do monitor sai no log do servidor (`C:\www\logs\server.log`, linhas `[monitorprecojogos]`)
e também em `logs\monitor.log` nesta pasta.

> Rode o monitor **em um lugar só**. Com ele no servidor, não use o `iniciar.bat` ao mesmo tempo:
> a mesma sessão do Telegram aberta em dois lugares pode ser derrubada.

## 1. Configurar (uma vez)
1. Dependências do Python (já instaladas nesta máquina; repita se trocar de Python):
   ```
   python -m pip install -r requirements.txt
   ```
2. Copie `segredos.exemplo.py` para `segredos.py` e preencha as chaves do Telegram; os canais ficam no `config.py` (veja o LEIA-ME).
3. Faça o login no Telegram **nesta máquina**, num Prompt de Comando nesta pasta (pede telefone e código):
   ```
   python codigo\listar_canais.py
   ```
   Se já usava em outro PC, pode só copiar o `precos.db`, a pasta `capas\`,
   o `sessao_usuario.session` e o `sessao_bot.session` para esta pasta.
4. Reinicie o servidor de `C:\www` (`stop.ps1` e depois `start-hidden.vbs`). Sem reiniciar, o monitor
   tenta de novo sozinho em até 5 minutos.

Acesse `http://localhost/Monitor_preco_jogos/` (ou pelo IP da máquina na rede).

## 2. Ajustes (opcional): `servidor\config.json`
```json
{
  "prefixo": "/Monitor_preco_jogos",
  "senha": "",
  "python": "",
  "portaPython": 8787
}
```
- **prefixo**: só aparece no log. O endereço real vem do nome da pasta.
- **senha**: vazia = sem senha. Preenchida, o navegador pede usuário (qualquer) e senha ao abrir os dados.
- **python**: vazio descobre sozinho (`python` ou `py -3`). Se não achar, coloque o caminho do `python.exe`
  (no JSON, use barras duplas: `"C:\\Users\\voce\\AppData\\Local\\Programs\\Python\\Python314\\python.exe"`).
- **portaPython**: porta interna (só este PC acessa). Troque se a 8787 estiver ocupada.
- **demo**: `true` mostra dados de demonstração, sem Telegram (bom para conferir o painel).

## Se algo der errado
| No log do servidor | O que fazer |
|---|---|
| `Preencha o config.py` | Coloque API_ID, API_HASH e BOT_TOKEN no `segredos.py` |
| `Não encontrei o Python` | Instale o Python com "Add to PATH" ou preencha `"python"` no config.json |
| `Falta fazer login no Telegram` | Rode `python codigo\listar_canais.py` nesta pasta; ele tenta de novo sozinho |
| `O monitor parou... Reiniciando` repetindo | As linhas logo acima dizem o motivo |
| Painel diz que o monitor não responde | O Python está iniciando ou caiu; veja o log |

## Parar
O `C:\www\stop.ps1` para o servidor **e** o Python do monitor (que guarda o PID em `logs\monitor.pid`).

## Acesso
- **Não abra a porta no roteador** por causa do painel. Para acessar fora de casa, prefira uma VPN (ex.: Tailscale).

## Atualizar para uma versão nova
Pare o servidor, substitua a pasta `codigo\`, a pasta `dist\`, `server\` e `servidor\monitor.js`
(mantenha `config.py`, `servidor\config.json`, `precos.db`, `capas\` e os `.session`) e inicie de novo.

## Backup
O banco grava as mudanças recentes em `precos.db-wal` antes de passar para o `precos.db`. Por isso, copiar só o
`precos.db` com o servidor ligado pode perder o que mudou por último. Faça assim (funciona com tudo ligado):
```
python -c "import sqlite3; sqlite3.connect('precos.db').backup(sqlite3.connect('backups/precos.db'))"
```
e copie também a pasta `capas\`. Com o servidor parado, copiar os três arquivos `precos.db*` também serve.

## Outras opções
- **Só no PC, sem o servidor:** `iniciar.bat` (o Python serve o painel em `http://localhost:8787`).
  Não use junto com o servidor de `C:\www`.

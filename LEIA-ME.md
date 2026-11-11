# Monitor de preços de jogos (Telegram)

> Esta pasta já está no servidor de `C:\www`: o painel abre em `http://localhost/Monitor_preco_jogos/`.
> Veja o **SERVIDOR.md** (é o jeito recomendado). O `iniciar.bat` abaixo é só para rodar avulso, sem o servidor.

## Instalação (uma vez só)

1. Extraia esta pasta em algum lugar, ex.: `C:\monitor_jogos`
2. Abra o **Prompt de Comando** nessa pasta (na barra de endereço do Explorer, digite `cmd` e Enter) e rode:
   ```
   pip install -r requirements.txt
   ```

## Configuração

### 1. Credenciais da sua conta
- Entre em https://my.telegram.org com seu número → **API development tools**
- Crie um app (nome e descrição quaisquer) e copie **api_id** e **api_hash** para `TG_API_ID` e `TG_API_HASH` no arquivo `.env` (copie antes o `.env.exemplo` com o nome `.env`; ele não vai para o GitHub)

### 2. Bot de alertas
- No Telegram, abra o **@BotFather** → `/newbot` → escolha nome e usuário
- Copie o **token** para `TG_BOT_TOKEN` no `.env`
- **Abra o seu bot e mande /start** (sem isso ele não consegue te mandar mensagem)

### 3. IDs dos canais
```
python codigo\listar_canais.py
```
Na primeira vez ele pede seu telefone (com +55) e o código que chega no Telegram.
Copie os IDs dos canais de promoção para `CANAIS` no `config.py`.

## Adicionar um canal
1. No Telegram, **entre no canal** com a sua conta (o monitor só recebe em tempo real os canais que você segue).
2. **Pare o servidor** (`C:\www\stop.ps1`): o próximo passo usa a mesma sessão do Telegram e as duas não
   podem ficar abertas ao mesmo tempo.
3. Num Prompt de Comando nesta pasta: `python codigo\listar_canais.py` e copie o ID do canal (começa com `-100`).
4. No `config.py`, acrescente uma linha em `CANAIS`, por exemplo:
   ```python
   {"id": -1002747000473, "nome": "PromoGames", "plataforma": None,
    "cortar_topo": 0.16, "cortar_base": 0.0},
   ```
   - `plataforma`: o console quando a mensagem não diz (use `None` se o canal mistura consoles)
   - `cortar_topo`/`cortar_base`: quanto da foto cortar para tirar a faixa com o logo do canal
5. Inicie o servidor de novo (`C:\www\start-hidden.vbs`). Na primeira vez ele importa os últimos 180 dias do canal
   novo, sem alertar.

Se as mensagens do canal novo não aparecerem no painel, o formato delas é diferente dos que o monitor conhece:
mande um print de uma oferta que o leitor é ajustado (veja `codigo/extrator.py`).

## Quer ver o painel antes de configurar?
Dê dois cliques em **ver-demo.bat**. Ele cria dados fictícios (`demo.db`) e abre o painel no navegador.
Nada disso se mistura com os seus dados reais.

## Rodar
Dê dois cliques em **iniciar.bat** (ou `python codigo\monitor.py`) e deixe a janela aberta.
O painel abre sozinho em **http://localhost:8787** (só no seu PC).

Na primeira execução ele importa os últimos 180 dias dos canais (só grava, sem alertar).
Nas próximas, busca o que chegou enquanto o PC estava desligado e alerta as ofertas das últimas 24h.

**Iniciar com o Windows (opcional):** aperte `Win+R`, digite `shell:startup` e coloque ali um atalho para o `iniciar.bat`.

## Painel (http://localhost:8787)
- **Busca:** digite o nome do jogo e veja o preço atual, o **menor já visto** (etiqueta amarela) e o preço normal
- **Detalhe do jogo:** gráfico com o histórico de preços e todas as ofertas, com link da loja e da mensagem original
- **Ofertas:** tudo que chegou nos canais, por dia, marcando os menores preços já vistos
- **Lista de desejos:** adicione ou remova jogos com o preço que você quer pagar (é a mesma lista do bot)

O painel atualiza sozinho a cada minuto.

### Mesmo jogo com nomes diferentes
Os canais escrevem o mesmo jogo de jeitos diferentes. O monitor junta sozinho quando a diferença é só
ruído ("(nacional)", "(Japonês)", "+ Brindes", "Day One", "Standard Edition", "liberada", "Remastered"),
grafia ("&" / "and", "Legend of Zelda" / "Zelda") ou erro de digitação. Edições (Deluxe, Gold, Steelbook,
Collector's...) e números diferentes ("Puyo Puyo Tetris" / "2S") ficam separados. As regras estão em
`codigo/semelhanca.py` e os casos testados em `codigo/testes/testar_repetidos.py`. Se sobrar algum repetido, abra um deles,
marque todas as ofertas e use **Mover selecionadas** para o outro. O monitor guarda o nome do item que sumiu como **apelido** do
que ficou (o mesmo vale para "Corrigir" com nome novo): ofertas futuras com aquele nome, no mesmo console,
já caem no item certo.

### Corrigir o que o monitor entendeu errado
Abra o jogo no painel:
- **Corrigir** (ao lado do selo do console): muda o jogo inteiro. Em **Tipo**: **Jogo**,
  **Bundle** ou **Colecionador** (saem da lista de jogos e não buscam preço digital, mas continuam alertando)
  ou **Acessório** (só alerta se estiver na lista de desejos). O filtro
  "Jogos / Bundles / Colecionador / Acessórios / Tudo" fica acima da lista. O monitor já marca sozinho; você só corrige quando ele errar.
  Consoles (sozinhos ou com jogo), monitores, teclados, fones/headsets, mouses, cadeiras e tudo que é só de Xbox são descartados. Se o mesmo jogo já existir
  no console escolhido, os dois viram um só.
- **Mover** (em cada linha de "Todas as ofertas"): leva só aquela oferta para o mesmo jogo em outro console
  (ex.: veio como PS5, mas a foto é de PS4) ou para outro jogo. Se o jogo ficar sem ofertas, ele some.
  Para mover **várias de uma vez**, marque as caixinhas na tabela (Shift + clique marca um intervalo; a do
  cabeçalho marca todas) e use **Mover selecionadas**.
- **Excluir jogo** (ao lado de "Corrigir"): apaga o jogo e todas as ofertas dele, depois de
  confirmar. Não dá para desfazer. Se o canal editar uma dessas mensagens, ela não volta; ofertas novas sim.
- **Colar capa**: copie uma imagem (botão direito → "Copiar imagem") e, com o jogo aberto, aperte **Ctrl+V**
  (ou use o botão "Colar capa"). Aparece uma prévia; confirme em **Usar como capa**. O botão só lê a área de
  transferência quando o painel é aberto pelo próprio PC (localhost); pelo IP da rede, use o Ctrl+V.
- **Trocar capa** (abaixo da capa): recorte a foto (arrastando ou com "Metade esquerda/direita..." para
  bundles e fotos com duas versões), envie outra imagem ou cole uma com Ctrl+V. "Voltar à foto original"
  desfaz.

Correções feitas assim não são desfeitas se o canal editar a mensagem depois.

### Já tenho / Não me interessa
Na ficha do jogo, os botões **Já tenho** e **Não me interessa** tiram o jogo das abas Jogos e Ofertas e
param os alertas de preço dele (a lista de desejos continua avisando). Nada é apagado: os filtros
"Já tenho" e "Não me interessa" (ao lado das plataformas) mostram só os marcados, e a busca acha todos.
Clique de novo no botão marcado para desfazer.

### Aba Revisar
O que o monitor não resolveu sozinho:
- **Possíveis repetidos:** nomes muito parecidos no mesmo console. "Ficar com este" junta as ofertas do outro
  nele (e o nome do outro passa a cair no lugar certo); "São diferentes" tira o par da fila.
- **Sem plataforma** e **Sem capa:** abra e corrija, ou dispense se estiver certo assim.

### Cupom
Clique no código do cupom (nas ofertas ou na tabela do jogo) e ele é copiado.

### Aba Saúde
Mostra se o monitor está ligado, a última mensagem de cada canal, o Deku Deals, o espaço usado e os
últimos avisos/erros do log. A bolinha no topo ("Monitor ligado") fica vermelha se algo parar.
Se um canal ficar `HORAS_SILENCIO_CANAL` (48 h) sem mandar nada, ou todos ficarem `HORAS_SILENCIO_GERAL`
(16 h) quietos, chega um aviso no seu Telegram (e outro quando voltar).

### Backups
1x por dia o monitor copia o banco para `backups/precos-auto-AAAAMMDD-HHMM.db` e apaga os mais antigos,
ficando os `BACKUPS_MANTER` (7) mais novos. Para voltar um backup: pare o servidor e copie o arquivo por
cima do `precos.db` (apague também `precos.db-wal` e `precos.db-shm`).

## Capas dos jogos
A capa vem da foto que o próprio canal manda junto com a oferta. O monitor baixa essa foto na
primeira vez que o jogo aparece, corta a faixa com o logo do canal e a margem branca, e salva em
`capas/`. Não usa nenhum site externo.

Se alguma capa sair com pedaço do logo do canal ou cortada demais, ajuste `cortar_topo` e
`cortar_base` daquele canal no `config.py` (0.15 = 15% da foto). Para gerar de novo a capa de um
jogo, apague o arquivo dele em `capas/` e espere a próxima oferta com foto.

## Físico ou digital?
Para cada jogo, o monitor consulta o **Deku Deals** (região Brasil) e pega o preço digital de hoje na
eShop / PlayStation Store / Microsoft Store e o **menor preço digital da história**. No painel, abra um jogo
e veja a seção "Físico ou digital?":
- **Vale o físico:** o físico está mais barato que o digital hoje *e* abaixo do menor preço digital já visto
- **Físico mais barato hoje:** ganha do digital agora, mas o digital já foi mais barato em promoção
- **Digital mais barato:** o digital está saindo por menos agora
- **Mesmo preço:** diferença pequena; o físico ainda pode ser revendido ou emprestado

Os alertas do bot também trazem essa comparação quando o preço digital já é conhecido.

Como funciona a consulta:
- Uma vez por dia por jogo, uma página por vez, com pausa entre elas (para não sobrecarregar o site).
- A busca é automática pelo nome. Se não achar ou achar o jogo errado, abra o jogo no painel,
  clique em **Colar link do Deku Deals** e cole o endereço da página dele (ex.: `https://www.dekudeals.com/items/astro-bot`).
- Testar a consulta na sua máquina: `python codigo\testes\testar_deku.py "Astro Bot" PS5`
- Se o Deku Deals mudar o layout, a leitura pode falhar; rode `python codigo\testes\testar_deku.py` e me mande o resultado.

## Comandos no seu bot
| Comando | O que faz |
|---|---|
| `/quero Elden Ring PS5 150` | avisa quando ficar até R$150 (plataforma é opcional) |
| `/lista` | mostra sua lista de desejos |
| `/remover 2` | remove o item 2 |
| `/historico zelda` | menor preço, preço normal e últimas ofertas |
| `/ultimas` | últimas ofertas registradas |

## Quando você é avisado
- 🎯 jogo da sua lista abaixo do preço-alvo
- 📉 menor preço já registrado (precisa de 3+ ofertas anteriores)
- 💸 25%+ abaixo do preço normal (mediana) do jogo
- 🔥 desconto anunciado de 50%+ ("De R$X por R$Y")

Todos os números ficam no fim do `config.py` para ajustar.

## Arquivos
- `precos.db` — seu histórico (pode abrir com o programa gratuito *DB Browser for SQLite*)
- `sessao_usuario.session` — **acesso à sua conta do Telegram. Não compartilhe.**
- `config.py` — suas configurações (o único `.py` fora da pasta `codigo/`)
- `codigo/` — todo o código Python do monitor (`monitor.py`, `api.py`, `extrator.py`, `deku.py`,
  `manutencao.py` etc.)
- `codigo/testes/` — testes: `testar_extrator.py` (leitura das mensagens), `testar_revisao.py`
  (correções da revisão), `testar_repetidos.py`, `testar_deku.py` (preço digital) e
  `testar_revisao_dados.py` (valor de cupom, loja digital, console e post de promoção que não são ofertas).
  Rode da pasta do monitor, ex.: `python codigo\testes\testar_extrator.py`
- `backups/` — cópias do banco (ficam as 7 mais novas)
- `capas/` — capas dos jogos, salvas automaticamente
- `dist/` — o painel já compilado (é o que abre no navegador)
- `server/api.js` e `servidor/` — integração com o servidor de `C:\www`
- `web/` — código-fonte do painel em React/Vite

## Mexer no painel (opcional, precisa do Node.js)
Instale o Node.js LTS em https://nodejs.org. Com o monitor (ou o `ver-demo.bat`) rodando:
```
cd web
npm install
npm run dev
```
Abra o endereço que aparecer (http://localhost:5173). As alterações aparecem na hora.
Quando terminar, `npm run build` atualiza a pasta `dist/`.

## Cuidados
- O script só **lê** mensagens com a sua conta. Não adicione nada que envie mensagens por ela.
- Se um canal mudar o formato das mensagens, mande um print novo que o extrator é ajustado.

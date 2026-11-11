# Monitor de preços de jogos (mídia física)

Lê canais de promoção de games no Telegram, guarda o histórico de preço de cada jogo, compara com o
preço digital (Deku Deals) e manda um aviso no **seu** bot do Telegram quando aparece um preço bom
ou um jogo da sua lista de desejos. Tem um painel no navegador com capas, histórico e filtros.

Roda no seu computador (Windows). Cada pessoa usa a **própria** conta do Telegram e o **próprio** bot.

---

## Instalação passo a passo

### 1. Instale o Python
Baixe o Python 3.10 ou mais novo em https://www.python.org/downloads/
Na instalação, **marque "Add python.exe to PATH"**.

### 2. Baixe o projeto
No GitHub, clique em **Code → Download ZIP** e extraia numa pasta (ex.: `C:\Monitor_preco_jogos`).
Ou, se tiver o Git: `git clone <endereço do repositório>`.

### 3. Instale as dependências
Abra um **Prompt de Comando** dentro da pasta do projeto e rode:
```
python -m pip install -r requirements.txt
```

### 4. Crie as suas chaves do Telegram
Copie o arquivo `.env.exemplo` e renomeie a cópia para `.env` (sem o ".exemplo"). Abra no Bloco de Notas e preencha:

- **TG_API_ID** e **TG_API_HASH**: entre em https://my.telegram.org com o seu número →
  *API development tools* → crie um app (nome e descrição quaisquer) → copie o *api_id* e o *api_hash*.
- **TG_BOT_TOKEN**: no Telegram, fale com o **@BotFather** → `/newbot` → escolha um nome → copie o token.
  Depois **abra o seu bot e mande `/start`** para ele (sem isso ele não consegue te avisar).

> O `.env` é só seu: **não compartilhe e não envie para o GitHub** (ele já está no `.gitignore`).

### 5. Entre nos canais de promoção
Com a sua conta do Telegram, entre nos canais que o monitor lê:

- https://t.me/ofertasnintendobr
- https://t.me/ofertasplaystationbr
- https://t.me/descontoemgames
- https://t.me/promogames_br
- https://t.me/promotecgames
- https://t.me/consumergames

(Para trocar a lista, edite `CANAIS` no `config.py` — veja o `LEIA-ME.md`.)

### 6. Faça o login do Telegram (uma vez só)
No Prompt de Comando, na pasta do projeto:
```
python codigo\listar_canais.py
```
Ele pede o seu número (com +55) e o código que chega no Telegram. No fim, lista os seus canais.
Isso cria o arquivo `sessao_usuario.session` — ele dá acesso à sua conta: **não compartilhe**.

### 7. Rode
Dê dois cliques em **`iniciar.bat`** e deixe a janela aberta. O painel abre em http://localhost:8787

Na primeira vez ele importa os últimos 180 dias dos canais (alguns minutos) e depois consulta os
preços digitais aos poucos. Os avisos no bot começam a chegar com as ofertas novas.

---

## Usando

- **Painel** (http://localhost:8787): busca, histórico de preço, "No menor preço agora", físico × digital,
  lista de desejos, aba **Revisar** (repetidos, sem plataforma, sem preço digital) e aba **Saúde**.
- **Bot**: `/quero Elden Ring PS5 150` avisa quando ficar até R$150; `/lista`, `/remover 2`,
  `/historico zelda`, `/ultimas`.
- **Ajustes** (plataformas ignoradas, regras de "preço bom", backups): fim do `config.py`.

Detalhes de tudo no **[LEIA-ME.md](LEIA-ME.md)**. Para rodar como serviço junto de outro servidor Node,
veja o **[SERVIDOR.md](SERVIDOR.md)**.

## Atualizar para uma versão nova
Baixe de novo (ou `git pull`) e **mantenha** na pasta: `.env`, `precos.db`, `capas\`, `backups\` e os
arquivos `.session`. Eles não estão no repositório, então não são apagados.

## O que nunca compartilhar
`.env`, `*.session` (acesso à sua conta do Telegram) e, se quiser privacidade, `precos.db`.

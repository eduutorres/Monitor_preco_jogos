"""
Monitor de preços de jogos em mídia física.
  - Lê os canais configurados com a SUA conta (somente leitura)
  - Grava cada oferta no banco precos.db
  - Avisa pelo seu bot quando um jogo da lista de desejos ou um preço muito bom aparece

Uso: python codigo/monitor.py   (deixe a janela aberta, ou rode como serviço no servidor)
"""
import asyncio
import logging
import os
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient, events

from raiz import RAIZ
import api
import banco
import capas
import deku
import config
import manutencao
from extrator import detectar_plataforma, extrair, menciona_esgotado, normalizar_nome

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%d/%m %H:%M")
log = logging.getLogger("monitor")
logging.getLogger("telethon").setLevel(logging.WARNING)

PASTA = RAIZ
SESSAO_USUARIO = str(api.PASTA_DADOS / "sessao_usuario")   # caminhos absolutos: funcionam como serviço
SESSAO_BOT = str(api.PASTA_DADOS / "sessao_bot")
db = banco.conectar(api.DB_PATH)
CANAIS = {c["id"]: c for c in config.CANAIS}
IGNORADAS = set(getattr(config, "PLATAFORMAS_IGNORADAS", []))
XBOX_IGNORADO = any(p.startswith("Xbox") for p in IGNORADAS)
usuario: TelegramClient
bot: TelegramClient
DONO: int = 0


class GuardarErros(logging.Handler):
    """Avisos e erros do log vão também para o banco: a página de saúde do painel mostra os últimos."""
    def emit(self, record):
        try:
            con = banco.conectar(api.DB_PATH)
            try:
                banco.registrar_erro(con, record.levelname, self.format(record))
            finally:
                con.close()
        except Exception:
            pass                                    # o log nunca pode derrubar o monitor


_guardar = GuardarErros(logging.WARNING)
_guardar.setFormatter(logging.Formatter("%(name)s: %(message)s"))
logging.getLogger().addHandler(_guardar)


# ================================================================ util
def brl(v) -> str:
    return "—" if v is None else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def link_da_mensagem(chat, msg_id: int) -> str:
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}/{msg_id}"
    return f"https://t.me/c/{str(chat.id).replace('-100', '')}/{msg_id}"


# ================================================================ processamento
async def processar_seguro(msg, alertar: bool = True):
    """Uma mensagem com problema não pode derrubar o monitor nem a importação."""
    try:
        await processar(msg, alertar)
    except Exception:
        log.exception(f"Erro ao processar a mensagem {getattr(msg, 'id', '?')} de {getattr(msg, 'chat_id', '?')}")
    finally:
        if getattr(msg, "chat_id", None) in CANAIS:
            banco.marcar_lida(db, msg.chat_id, msg.id, getattr(msg, "date", None))


async def processar(msg, alertar: bool = True):
    canal_cfg = CANAIS.get(msg.chat_id)
    if not canal_cfg:
        return
    texto = msg.message or ""

    # "Cupom esgotado" respondendo a uma oferta → marca a oferta como inativa
    if menciona_esgotado(texto) and msg.reply_to_msg_id:
        banco.marcar_esgotado(db, msg.chat_id, msg.reply_to_msg_id)

    oferta = extrair(texto, canal_cfg.get("plataforma"))
    if not oferta or oferta.plataforma in IGNORADAS:
        return
    # "Controle sem fio XBOX" não diz "Series": se o Xbox é ignorado, qualquer item só de Xbox sai
    if XBOX_IGNORADO and not oferta.plataforma and re.search(r"\bxbox\b", oferta.jogo, re.I):
        return
    if banco.mensagem_excluida(db, msg.chat_id, msg.id):
        return  # você excluiu essa oferta no painel; a edição da mensagem não a traz de volta

    await guardar_capa(msg, oferta, canal_cfg)

    chat = await msg.get_chat()
    link_msg = link_da_mensagem(chat, msg.id)
    resultado = banco.registrar_oferta(db, oferta, msg.chat_id, msg.id, msg.date, link_msg)
    if menciona_esgotado(texto):
        banco.marcar_esgotado(db, msg.chat_id, msg.id)
    if resultado is None:
        return  # repetida ou edição

    jogo_id, oferta_id = resultado
    log.info(f"💾 {oferta.jogo} [{oferta.plataforma}] {brl(oferta.preco)} — {oferta.loja}")
    if alertar:
        await checar_alertas(jogo_id, oferta_id, oferta, link_msg)


async def guardar_capa(msg, oferta, canal_cfg):
    """Usa a foto da mensagem como capa do jogo (só na primeira vez que ela aparece)."""
    if not getattr(msg, "photo", None):
        return
    jogo_id = banco.obter_ou_criar_jogo(db, oferta)
    if banco.capa_do_jogo(db, jogo_id):
        return
    try:
        dados = await msg.download_media(file=bytes)
        arquivo = capas.salvar_capa(api.PASTA_CAPAS, jogo_id, dados,
                                    canal_cfg.get("cortar_topo", 0), canal_cfg.get("cortar_base", 0))
        banco.definir_capa(db, jogo_id, arquivo)
        log.info(f"🖼  Capa salva: {oferta.jogo}")
    except Exception as e:
        log.warning(f"Não consegui salvar a capa de {oferta.jogo}: {e}")


def linha_menor_preco(jogo_id: int, oferta_id: int, preco: float) -> str:
    """'📊 Menor já registrado: R$ 129,00 (Amazon, 26/06/26)', comparado com as ofertas de antes desta."""
    m = db.execute("SELECT preco, loja, data FROM ofertas WHERE jogo_id=? AND id<>? ORDER BY preco, data LIMIT 1",
                   (jogo_id, oferta_id)).fetchone()
    if not m:
        return "📊 Primeira oferta registrada deste jogo"
    onde = f"{m['loja'] or 'loja ?'}, {datetime.fromisoformat(m['data']).astimezone():%d/%m/%y}"
    if preco < m["preco"]:
        return f"📊 Novo menor preço! O anterior era {brl(m['preco'])} ({onde})"
    if preco == m["preco"]:
        return f"📊 Igual ao menor já registrado ({onde})"
    return f"📊 Menor já registrado: {brl(m['preco'])} ({onde})"


async def checar_alertas(jogo_id, oferta_id, oferta, link_msg):
    motivos = []
    # Nome e console do jogo CADASTRADO, não o que a mensagem trouxe: o canal de PlayStation assume PS5
    # quando a mensagem não diz, e uma oferta de jogo que você corrigiu para PS4 cai nele pelo apelido.
    j = db.execute("SELECT nome, chave, plataforma FROM jogos WHERE id=?", (jogo_id,)).fetchone()
    nome = j["nome"] if j else oferta.jogo
    chave = j["chave"] if j else oferta.chave
    plataforma = j["plataforma"] if j else oferta.plataforma

    for d in banco.listar_desejos(db):
        if banco.desejo_combina(d, chave, plataforma) and oferta.preco <= d["preco_alvo"]:
            motivos.append(f"🎯 Na sua lista! Alvo: {brl(d['preco_alvo'])}")
            break

    # acessório/console (marcado no painel): só o alerta da lista de desejos
    # bundle e colecionador alertam como jogo; acessório só pela lista de desejos
    # "já tenho"/"não me interessa" (marcado no painel): também só pela lista de desejos
    tipo_item = banco.tipo_do_jogo(db, jogo_id)
    if banco.marca_do_jogo(db, jogo_id):
        tipo_item = "marcado"
    if tipo_item in ("jogo", "bundle", "colecionador") and (not oferta.prevenda or config.ALERTAR_PREVENDA or motivos):
        anteriores = banco.precos_anteriores(db, jogo_id, oferta_id)
        if len(anteriores) >= config.MIN_REGISTROS:
            minimo, mediana = min(anteriores), statistics.median(anteriores)
            if oferta.preco < minimo:
                motivos.append(f"📉 Menor preço já registrado (antes: {brl(minimo)})")
            elif oferta.preco <= mediana * (1 - config.DESCONTO_MEDIANA):
                pct = round(100 * (1 - oferta.preco / mediana))
                motivos.append(f"💸 {pct}% abaixo do preço normal ({brl(mediana)})")
        if oferta.desconto and oferta.desconto >= config.DESCONTO_ANUNCIADO:
            motivos.append(f"🔥 {oferta.desconto}% de desconto sobre {brl(oferta.preco_de)}")

    if not motivos or banco.alerta_ja_enviado(db, jogo_id, oferta.preco):
        return

    dig = deku.dados_digitais(db, jogo_id) if tipo_item == "jogo" else None   # digital só p/ jogo comum
    anteriores_todos = banco.precos_anteriores(db, jogo_id, oferta_id, dias=3650)
    v = deku.veredito(oferta.preco, min(anteriores_todos + [oferta.preco]), dig)  # oferta de agora: sem aviso de data

    extras = [x for x, ok in [("PIX", oferta.pix), ("frete grátis", oferta.frete_gratis),
                              ("pré-venda", oferta.prevenda)] if ok]
    texto = (
        f"🎮 **{nome}** ({plataforma or '?'})\n"
        f"💰 **{brl(oferta.preco)}**"
        + (f"  ~~{brl(oferta.preco_de)}~~" if oferta.preco_de else "")
        + f"\n🏪 {oferta.loja or '?'}"
        + (f" · {', '.join(extras)}" if extras else "")
        + (f"\n🏷 Cupom: `{oferta.cupom}`" if oferta.cupom else "")
        + f"\n{linha_menor_preco(jogo_id, oferta_id, oferta.preco)}"
        + "\n\n" + "\n".join(motivos)
        + (f"\n\n💻 Digital: {brl(dig['preco_atual'])} agora, menor {brl(dig['menor_preco'])}\n"
           f"{'✅' if v['tipo'] in ('fisico', 'empate') else '⚖️' if v['tipo'] == 'fisico_hoje' else '💻'} {v['titulo']}: {v['texto']}"
           if v else "")
        + (f"\n\n🛒 {oferta.link}" if oferta.link else "")
        + f"\n📨 [Ver mensagem original]({link_msg})"
    )
    try:
        await bot.send_message(DONO, texto, link_preview=False)
    except Exception as e:
        log.error(f"Não consegui enviar o alerta de {nome} ({e}). "
                  "Você já mandou /start para o seu bot no Telegram?")
        return
    banco.registrar_alerta(db, jogo_id, oferta.preco)
    log.info(f"🔔 Alerta enviado: {nome} [{plataforma}]")


# ================================================================ histórico
async def importar_historico():
    """Busca o que chegou enquanto o PC estava desligado (ou o histórico, na 1ª vez)."""
    for canal_id, cfg in CANAIS.items():
        ultimo = banco.ultimo_msg_id(db, canal_id)
        try:
            entidade = await usuario.get_entity(canal_id)
        except Exception as e:
            log.error(f"❌ Não consegui abrir o canal {cfg.get('nome', canal_id)}: {e}")
            continue
        if ultimo:
            log.info(f"⏩ {cfg.get('nome')}: buscando mensagens novas desde a última execução")
            iterador = usuario.iter_messages(entidade, min_id=ultimo, reverse=True)
            alertar_recentes = True
        else:
            dias = config.DIAS_HISTORICO_INICIAL
            log.info(f"📥 {cfg.get('nome')}: importando os últimos {dias} dias (pode demorar)")
            inicio = datetime.now(timezone.utc) - timedelta(days=dias)
            iterador = usuario.iter_messages(entidade, offset_date=inicio, reverse=True)
            alertar_recentes = False
        n = 0
        limite_alerta = datetime.now(timezone.utc) - timedelta(hours=24)
        async for msg in iterador:
            await processar_seguro(msg, alertar=alertar_recentes and msg.date >= limite_alerta)
            n += 1
        log.info(f"   {n} mensagens lidas")


REVISAO_MIN = 10          # de quanto em quanto tempo relê as últimas mensagens de cada canal
REVISAO_MENSAGENS = 40    # quantas mensagens recentes por canal


async def faxina_capas():
    """Ao ligar e 1x por dia: apaga capas que nenhum item usa (não deixa a pasta crescer à toa)."""
    while True:
        try:
            n, b = capas.limpar_orfas(api.PASTA_CAPAS, db)
            if n:
                log.info(f"🧹 Capas sem uso apagadas: {n} ({b / 1024 / 1024:.1f} MB)")
        except Exception as e:
            log.warning(f"Faxina das capas falhou: {e}")
        await asyncio.sleep(24 * 3600)


BATIDA_MIN = 5            # de quanto em quanto tempo o monitor avisa o painel que está vivo


def _quando(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone().strftime("%d/%m %H:%M")


async def avisar(texto: str):
    try:
        await bot.send_message(DONO, texto, link_preview=False)
    except Exception as e:
        log.error(f"Não consegui mandar o aviso pelo bot ({e}): {texto}")


async def vigia():
    """
    A cada 5 min confere os canais (começa depois da busca das atrasadas, senão avisaria à toa).
    Canal sem mensagem há mais que o limite (ou todos quietos há horas) = aviso no Telegram, uma vez;
    quando voltar a chegar mensagem, avisa que voltou.
    """
    while True:
        try:
            s = api.saude(db)
            itens = [(f"silencio:{c['id']}", c["parado"], c["nome"], c["ultima_mensagem"], c["limite_horas"])
                     for c in s["canais"]]
            g = s["silencio_geral"]
            ultima = max((c["ultima_mensagem"] for c in s["canais"] if c["ultima_mensagem"]), default=None)
            itens.append(("silencio:geral", g["parado"], None, ultima, g["limite_horas"]))
            for chave, parado, nome, desde, limite in itens:
                avisado, _ = banco.ler_estado(db, chave)
                if parado and not avisado:
                    quem = f"O canal **{nome}** não manda" if nome else "**Nenhum canal** mandou"
                    await avisar(f"⚠️ {quem} nada há mais de {limite} h (última mensagem em {_quando(desde)}).\n"
                                 "Pode ser a conexão com o Telegram, o canal ter parado ou sua conta ter saído dele. "
                                 "Veja a aba Saúde no painel.")
                    banco.definir_estado(db, chave, desde)
                    log.warning(f"Aviso de silêncio enviado: {nome or 'todos os canais'}")
                elif not parado and avisado:
                    quem = f"O canal **{nome}**" if nome else "Os canais"
                    await avisar(f"✅ {quem} voltou a mandar mensagens.")
                    banco.apagar_estado(db, chave)
        except Exception as e:
            log.warning(f"Vigia do monitor falhou: {e}")
        await asyncio.sleep(BATIDA_MIN * 60)


async def batimento():
    """Sinal de vida para o painel (começa antes da busca das mensagens atrasadas, que pode demorar)."""
    while True:
        try:
            banco.definir_estado(db, "batida")
            banco.definir_estado(db, "telegram", "1" if usuario.is_connected() else "0")
        except Exception as e:
            log.warning(f"Sinal de vida do monitor falhou: {e}")
        await asyncio.sleep(BATIDA_MIN * 60)


async def backup_diario():
    """1x por dia: copia o banco para backups/ e apaga os mais antigos (fica BACKUPS_MANTER)."""
    manter = getattr(config, "BACKUPS_MANTER", 7)
    while True:
        try:
            _, ultimo = banco.ler_estado(db, "backup")
            if not ultimo or datetime.now(timezone.utc) - datetime.fromisoformat(ultimo) >= timedelta(hours=24):
                arquivo, apagados = await asyncio.to_thread(
                    manutencao.fazer_backup, api.DB_PATH, api.PASTA_BACKUPS, manter)
                banco.definir_estado(db, "backup", arquivo.name)
                log.info(f"💾 Backup do banco: {arquivo.name}"
                         + (f" ({len(apagados)} antigo(s) apagado(s), ficam {manter})" if apagados else ""))
        except Exception as e:
            log.warning(f"Backup do banco falhou: {e}")
        await asyncio.sleep(3600)                   # confere de hora em hora se já deu 24 h


async def revisar_canais():
    """
    Rede de segurança: se a conexão com o Telegram cair, mensagens que chegaram no meio podem não
    passar pelo tempo real, e a busca de atrasadas não as pega (ela começa depois da última lida).
    Relê as últimas mensagens de cada canal; as já gravadas não mudam nem alertam de novo.
    """
    while True:
        await asyncio.sleep(REVISAO_MIN * 60)
        antes = db.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0]
        for canal_id, cfg in CANAIS.items():
            try:
                async for msg in usuario.iter_messages(canal_id, limit=REVISAO_MENSAGENS):
                    if db.execute("SELECT 1 FROM ofertas WHERE canal_id=? AND msg_id=?", (canal_id, msg.id)).fetchone():
                        continue                           # já gravada: nada a fazer
                    recente = msg.date >= datetime.now(timezone.utc) - timedelta(hours=24)
                    await processar_seguro(msg, alertar=recente)
            except Exception as e:
                log.warning(f"Revisão do canal {cfg.get('nome', canal_id)} falhou: {e}")
        novas = db.execute("SELECT COUNT(*) FROM ofertas").fetchone()[0] - antes
        if novas > 0:
            log.info(f"🔁 Revisão dos canais: {novas} oferta(s) que tinham escapado foram gravadas")


# ================================================================ comandos do bot
AJUDA = """🎮 **Monitor de preços**

/quero `nome [plataforma] preço` — avisa quando ficar abaixo do preço
  ex.: `/quero Elden Ring PS5 150`
/lista — sua lista de desejos
/remover `n` — remove o item n da lista
/historico `nome` — menor preço, preço normal e últimas ofertas
/ultimas — últimas ofertas registradas"""


async def comando(event):
    if event.sender_id != DONO:
        return
    try:
        await executar_comando(event)
    except Exception:
        log.exception("Erro no comando do bot")
        await event.reply("Deu um erro ao processar esse comando. Veja o log do monitor.")


async def executar_comando(event):
    partes = event.raw_text.strip().split(maxsplit=1)
    cmd, arg = partes[0].lower().split("@")[0], (partes[1] if len(partes) > 1 else "")

    if cmd in ("/start", "/ajuda", "/help"):
        await event.reply(AJUDA)

    elif cmd == "/quero":
        m = re.match(r"(.+?)\s+(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s*$", arg, re.I)
        if not m:
            return await event.reply("Use: `/quero Elden Ring PS5 150`")
        nome, alvo = m.group(1), float(m.group(2).replace(",", "."))
        plataforma = detectar_plataforma(nome)
        banco.adicionar_desejo(db, nome, normalizar_nome(nome), plataforma, alvo)
        resp = f"✅ Vou avisar quando **{nome}** ficar até {brl(alvo)}"
        achados = banco.buscar_jogos(db, nome, 1)
        if achados:
            r = banco.resumo_jogo(db, achados[0]["id"])
            resp += (f"\n\n📊 Histórico de *{r['jogo']['nome']}*: menor {brl(r['minimo'])}, "
                     f"normal {brl(r['mediana'])} ({r['total']} ofertas)")
        await event.reply(resp)

    elif cmd == "/lista":
        desejos = banco.listar_desejos(db)
        if not desejos:
            return await event.reply("Lista vazia. Use /quero para adicionar.")
        await event.reply("\n".join(f"{d['id']}. {d['texto']} — até {brl(d['preco_alvo'])}"
                                    for d in desejos))

    elif cmd == "/remover":
        ok = arg.isdigit() and banco.remover_desejo(db, int(arg))
        await event.reply("🗑 Removido." if ok else "Não achei esse número. Veja /lista.")

    elif cmd == "/historico":
        jogos = banco.buscar_jogos(db, arg) if arg else []
        if not jogos:
            return await event.reply("Não achei esse jogo no histórico.")
        blocos = []
        for j in jogos[:3]:
            r = banco.resumo_jogo(db, j["id"])
            linhas = [f"🎮 **{j['nome']}** ({j['plataforma'] or '?'})",
                      f"Menor: {brl(r['minimo'])} · Normal: {brl(r['mediana'])} · {r['total']} ofertas"]
            for o in r["ultimas"]:
                data = datetime.fromisoformat(o["data"]).strftime("%d/%m/%y")
                linhas.append(f"  {data} — {brl(o['preco'])} {o['loja'] or ''}"
                              + (" (esgotou)" if not o["ativo"] else ""))
            blocos.append("\n".join(linhas))
        await event.reply("\n\n".join(blocos))

    elif cmd == "/ultimas":
        rows = banco.ultimas_ofertas(db)
        await event.reply("\n".join(
            f"{brl(o['preco'])} — {o['nome']} ({o['plataforma'] or '?'}) · {o['loja'] or ''}"
            for o in rows) or "Nada registrado ainda.")


# ================================================================ main
async def main():
    global usuario, bot, DONO
    if str(config.API_HASH).startswith("cole_") or "cole_o_token" in str(config.BOT_TOKEN):
        log.error("Preencha o .env (TG_API_ID, TG_API_HASH e TG_BOT_TOKEN do Telegram): copie o .env.exemplo — veja o README.md.")
        sys.exit(1)
    api.iniciar_em_segundo_plano(getattr(config, "PORTA_PAINEL", 8787), getattr(config, "HOST_PAINEL", "127.0.0.1"))
    usuario = TelegramClient(SESSAO_USUARIO, config.API_ID, config.API_HASH)
    bot = TelegramClient(SESSAO_BOT, config.API_ID, config.API_HASH)

    await usuario.connect()
    if not await usuario.is_user_authorized():
        # no Windows o NUL conta como terminal, por isso o servidor Node avisa pela variável
        if os.environ.get("MONITOR_SEM_TERMINAL") or not sys.stdin.isatty():
            log.error("A conta do Telegram ainda não fez login neste computador. Rode uma vez, num "
                      "terminal, `python listar_canais.py` (ele pede telefone e código) e depois inicie o serviço.")
            sys.exit(1)
    await usuario.start()                      # 1ª vez: pede telefone e código
    await bot.start(bot_token=config.BOT_TOKEN)
    DONO = (await usuario.get_me()).id

    ids = list(CANAIS)
    usuario.add_event_handler(lambda e: processar_seguro(e.message), events.NewMessage(chats=ids))
    usuario.add_event_handler(lambda e: processar_seguro(e.message), events.MessageEdited(chats=ids))
    bot.add_event_handler(comando, events.NewMessage(pattern=r"^/"))

    banco.definir_estado(db, "inicio")
    vivo = asyncio.create_task(batimento())  # noqa: F841 (guardado para o asyncio não descartar a tarefa)
    deku.iniciar_atualizador(api.DB_PATH, log.info)   # preços digitais, em segundo plano
    await importar_historico()
    log.info("👀 Monitorando...")
    await asyncio.gather(usuario.run_until_disconnected(), bot.run_until_disconnected(), revisar_canais(),
                         faxina_capas(), vigia(), backup_diario())


if __name__ == "__main__":
    asyncio.run(main())

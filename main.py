from webserver import iniciar_web
import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
from discord.utils import get
import json
import os
import unicodedata
import time
import re
import aiohttp  # no topo do seu arquivo
from dotenv import load_dotenv

iniciar_web()

checar_mortes_ativo = True  # Estado inicial: checar mortes está ativado

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))  # ID do servidor
CANAL_PONTOS_ID = int(os.getenv("CANAL_PONTOS_ID"))  # Canal onde os pontos serão armazenados
CANAL_RANKING_ID = int(os.getenv("CANAL_RANKING_ID"))  # Canal de ranking
CANAL_MORTES_ID = int(os.getenv("CANAL_MORTES_ID"))


# Configuração do bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

VOCACOES = {
    "Royal Paladin": "[RP]",
    "Paladin": "[P]",
    "Elite Knight": "[EK]",
    "Knight": "[K]",
    "Elder Druid": "[ED]",
    "Druid": "[D]",
    "Master Sorcerer": "[MS]",
    "Sorcerer": "[S]"
}

listas_file = "listas.json"
mensagens_file = "mensagens.json"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

def carregar_mortes():
    if not os.path.exists("mortes.json"):
        return []
    with open("mortes.json", "r") as f:
        return json.load(f)

def salvar_mortes(mortes):
    with open("mortes.json", "w") as f:
        json.dump(mortes, f)

def normalizar_nome(nome):
    return unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII").lower().strip()

def carregar_listas():
    if not os.path.exists(listas_file):
        return {}
    with open(listas_file, "r") as f:
        return json.load(f)

def salvar_listas(dados):
    with open(listas_file, "w") as f:
        json.dump(dados, f)

def carregar_mensagens():
    if not os.path.exists(mensagens_file):
        return {}
    with open(mensagens_file, "r") as f:
        return json.load(f)

def salvar_mensagens(dados):
    with open(mensagens_file, "w") as f:
        json.dump(dados, f)

async def verificar_ultima_morte(nome):
    url = f"https://miracle74.com/?subtopic=characters&name={nome}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")

    # Procura por todas as tabelas
    tabelas = soup.find_all("table", {"class": "TableContent"})
    for tabela in tabelas:
        titulo = tabela.find_previous("b")
        if titulo and "Deaths" in titulo.text:
            linhas = tabela.find_all("tr")[1:]  # Ignora o header
            if not linhas:
                return None
            colunas = linhas[0].find_all("td")
            if colunas and len(colunas) >= 1:
                return colunas[0].text.strip()

    return None

async def verificar_status(nome):
    url = "https://miracle74.com/?subtopic=whoisonline"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    tabelas = soup.find_all("table", {"class": "TableContent"})
    personagens_info = []

    for tabela in tabelas:
        linhas = tabela.find_all("tr")[1:]
        for linha in linhas:
            colunas = linha.find_all("td")
            if colunas and len(colunas) >= 4:
                nome_completo = colunas[1].find("a").text.strip()
                level = colunas[2].text.strip()
                vocacao = colunas[3].text.strip()

                match = re.match(r"([a-zA-ZÀ-ÿ\s'\-]+)", nome_completo)
                if match:
                    nome_personagem = match.group(1).strip()
                    if nome_personagem:
                        personagens_info.append({
                            "nome": nome_personagem,
                            "level": level,
                            "vocacao": vocacao
                        })

    nome_normalizado = normalizar_nome(nome)
    for personagem in personagens_info:
        if normalizar_nome(personagem["nome"]) == nome_normalizado:
            voc_abrev = VOCACOES.get(personagem["vocacao"], personagem["vocacao"])
            return f"{voc_abrev} - {personagem['level']} 🟢"
    
    return None

@tasks.loop(seconds=30)
async def checar_mortes_globais():
    if not checar_mortes_ativo:  # Se a checagem de mortes estiver desativada, retorna imediatamente
        return

    print("[DEBUG] Verificando mortes globais...")
    listas = carregar_listas()
    mortes_anteriores = carregar_mortes()
    canal = bot.get_channel(CANAL_MORTES_ID)

    nomes_monitorados = set(normalizar_nome(nome) for nomes in listas.values() for nome in nomes)
    print(f"[DEBUG] Nomes monitorados: {nomes_monitorados}")

    url = "https://miracle74.com/?subtopic=latestdeaths"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()

    # Faz uma busca simples por texto
    soup = BeautifulSoup(html, "html.parser")
    texto_pagina = soup.get_text(separator="\n")

    for linha in texto_pagina.splitlines():
        linha = linha.strip()
        if not linha:
            continue

        for nome_monitorado in nomes_monitorados:
            if nome_monitorado in normalizar_nome(linha):
                ultima_morte = mortes_anteriores.get(nome_monitorado)
                
                # Se a morte já foi registrada anteriormente, ignora
                if ultima_morte == linha:
                    print(f"[DEBUG] Morte já registrada para {nome_monitorado}: {linha}")
                    continue  # Ignora e passa para a próxima linha de morte

                print(f"[DEBUG] Nova morte detectada: {linha}")
                mortes_anteriores[nome_monitorado] = linha
                await canal.send(f"☠️ **{nome_monitorado} morreu!**\nMorte: {linha}")

    salvar_mortes(mortes_anteriores)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    checar_status.start()
    checar_mortes_globais.start()

# (Comandos do bot... os comandos restantes aqui sem alterações)
@bot.command()
@checar_permissao()
async def startdeaths(ctx):
    global checar_mortes_ativo
    if checar_mortes_ativo:
        await ctx.send("A checagem de mortes já está ativada.")
    else:
        checar_mortes_ativo = True
        checar_mortes_globais.start()  # Inicia o loop da checagem de mortes
        await ctx.send("A checagem de mortes foi ativada.")

@bot.command()
@checar_permissao()
async def stopdeaths(ctx):
    global checar_mortes_ativo
    if not checar_mortes_ativo:
        await ctx.send("A checagem de mortes já está desativada.")
    else:
        checar_mortes_ativo = False
        checar_mortes_globais.stop()  # Para o loop da checagem de mortes
        await ctx.send("A checagem de mortes foi desativada.")


@bot.command()
@checar_permissao()
async def addguild(ctx, link, *, lista):
    listas = carregar_listas()
    if lista not in listas:
        await ctx.send(f"❌ Lista **{lista}** não existe.")
        return

    try:
        resposta = requests.get(link)
        soup = BeautifulSoup(resposta.text, "html.parser")
        tabela = soup.find("table", {"class": "TableContent"})

        if not tabela:
            await ctx.send("❌ Tabela de guilda não encontrada.")
            return

        nomes_adicionados = []
        linhas = tabela.find_all("tr")[1:]
        for linha in linhas:
            colunas = linha.find_all("td")
            if colunas and len(colunas) > 1:
                # Captura da segunda coluna (nome)
                raw_nome = colunas[1].get_text(strip=True)

                # Remove parênteses com conteúdo
                nome = re.sub(r"\\s*\\(.*?\\)", "", raw_nome).strip()

                if nome and nome not in listas[lista]:
                    listas[lista].append(nome)
                    nomes_adicionados.append(nome)

        salvar_listas(listas)
        await ctx.send(f"✅ {len(nomes_adicionados)} personagens adicionados à lista **{lista}**.")
    except Exception as e:
        await ctx.send(f"Erro ao adicionar guild: {e}")


@bot.command()
@checar_permissao()
async def addlist(ctx, *, nome_lista):
    guild = ctx.guild
    listas = carregar_listas()
    mensagens = carregar_mensagens()

    if nome_lista in listas:
        await ctx.send(f"A lista **{nome_lista}** já existe.")
        return

    canal = discord.utils.get(guild.text_channels, name=nome_lista.lower().replace(" ", "-"))
    if not canal:
        canal = await guild.create_text_channel(nome_lista.lower().replace(" ", "-"))

    listas[nome_lista] = []
    mensagens[nome_lista] = None
    salvar_listas(listas)
    salvar_mensagens(mensagens)
    await ctx.send(f"✅ Lista **{nome_lista}** criada com sucesso!")

@bot.command()
@checar_permissao()
async def removelist(ctx, *, nome_lista):
    listas = carregar_listas()
    mensagens = carregar_mensagens()

    if nome_lista not in listas:
        await ctx.send(f"❌ Lista **{nome_lista}** não encontrada.")
        return

    del listas[nome_lista]
    salvar_listas(listas)

    if nome_lista in mensagens:
        del mensagens[nome_lista]
        salvar_mensagens(mensagens)

    canal = discord.utils.get(ctx.guild.text_channels, name=nome_lista.lower().replace(" ", "-"))
    if canal:
        await canal.delete()

    await ctx.send(f"🗑️ Lista **{nome_lista}** e canal deletados com sucesso.")

@bot.command()
@checar_permissao()
async def remove(ctx, *, args):
    try:
        nome, lista = args.rsplit(" ", 1)
        lista = lista.strip()
    except ValueError:
        await ctx.send("❌ Use: `!remove <nome_personagem> <nome_lista>`")
        return

    listas = carregar_listas()
    if lista not in listas:
        await ctx.send(f"❌ Lista **{lista}** não encontrada.")
        return

    if nome not in listas[lista]:
        await ctx.send(f"❌ O personagem **{nome}** não está na lista **{lista}**.")
        return

    listas[lista].remove(nome)
    salvar_listas(listas)
    await ctx.send(f"✅ Personagem **{nome}** removido da lista **{lista}**.")

@bot.command()
@checar_permissao()
async def list(ctx, *, nome_lista):
    listas = carregar_listas()
    if nome_lista not in listas:
        await ctx.send(f"❌ Lista **{nome_lista}** não encontrada.")
        return

    personagens = listas[nome_lista]
    if not personagens:
        await ctx.send(f"A lista **{nome_lista}** está vazia.")
        return

    msg = f"**📋 Personagens monitorados em `{nome_lista}`:**\n" + "\n".join(f"- {p}" for p in personagens)
    await ctx.send(msg)

@bot.command()
@checar_permissao()
async def commands(ctx):
    msg = (
        "**🤖 Comandos disponíveis:**\n"
        "`!add list <nome_lista>` — cria uma nova lista\n"
        "`!add <personagem> <lista>` — adiciona personagem à lista\n"
        "`!remove list <nome_lista>` — apaga uma lista e o canal\n"
        "`!remove <personagem> <lista>` — remove personagem da lista\n"
        "`!list <lista>` — mostra todos os personagens (online e offline)\n"
        "`!commands` — mostra este painel de ajuda"
    )
    await ctx.send(msg)

@bot.command()
@checar_permissao()
async def add(ctx, *, args):
    try:
        nome, lista = args.rsplit(" ", 1)
        lista_normalizada = lista.strip()
    except ValueError:
        await ctx.send("❌ Formato incorreto. Use: `!add <nome_personagem> <nome_lista>`")
        return

    listas = carregar_listas()
    if lista_normalizada not in listas:
        await ctx.send(f"❌ Lista **{lista_normalizada}** não existe.")
        return

    if nome in listas[lista_normalizada]:
        await ctx.send(f"🔁 O personagem **{nome}** já está na lista **{lista_normalizada}**.")
        return

    listas[lista_normalizada].append(nome)
    salvar_listas(listas)
    await ctx.send(f"✅ Personagem **{nome}** adicionado à lista **{lista_normalizada}**.")

@tasks.loop(seconds=30)
async def checar_status():
    listas = carregar_listas()
    mensagens = carregar_mensagens()

    for nome_lista, personagens in listas.items():
        status_msg = f"📋 **{nome_lista}** - Monitoramento de personagens online:\n\n"
        resultados = []

        for nome in personagens:
            status = await verificar_status(nome)
            if status:
                match = re.search(r"(\d+)", status)
                level = int(match.group(1)) if match else 0
                resultados.append({"nome": nome, "status": status, "level": level})

        resultados = sorted(resultados, key=lambda x: x["level"], reverse=True)
        if resultados:
            status_msg += "\n".join(f"**{r['nome']}**: {r['status']}" for r in resultados)
        else:
            status_msg += "Nenhum personagem online no momento."

        guild = discord.utils.get(bot.guilds, id=GUILD_ID)
        canal = discord.utils.get(guild.text_channels, name=nome_lista.lower().replace(" ", "-"))
        if not canal:
            continue

        try:
            msg_id = mensagens.get(nome_lista)
            if msg_id:
                mensagem = await canal.fetch_message(int(msg_id))
                await mensagem.edit(content=status_msg)
            else:
                mensagem = await canal.send(status_msg)
                mensagens[nome_lista] = mensagem.id
                salvar_mensagens(mensagens)
        except Exception as e:
            print(f"[ERRO]: {e}")

bot = commands.Bot(command_prefix="!", intents=intents)

async def obter_pontos():
    """Obter pontos dos usuários do canal de pontos."""
    guild = discord.utils.get(bot.guilds, id=GUILD_ID)
    canal = discord.utils.get(guild.text_channels, id=CANAL_PONTOS_ID)

    pontos = {}

    if canal:
        async for mensagem in canal.history(limit=100):  # Limitar para 100 mensagens mais recentes
            if mensagem.author != bot.user:
                # Cada mensagem segue o formato: "nome: pontos"
                try:
                    nome, pontos_usuario = mensagem.content.split(": ")
                    pontos[nome] = int(pontos_usuario)
                except ValueError:
                    pass  # Se a mensagem não seguir o formato esperado, ignoramos

    return pontos

async def salvar_pontos():
    """Salvar os pontos atualizados no canal de pontos."""
    guild = discord.utils.get(bot.guilds, id=GUILD_ID)
    canal = discord.utils.get(guild.text_channels, id=CANAL_PONTOS_ID)

    if canal:
        pontos = await obter_pontos()

        # Deletar mensagens antigas de pontos
        async for mensagem in canal.history(limit=100):
            if mensagem.author == bot.user:
                await mensagem.delete()

        # Criar uma nova mensagem para cada usuário com seus pontos
        for usuario, pontos_usuario in pontos.items():
            await canal.send(f"{usuario}: {pontos_usuario}")

async def atualizar_ranking():
    """Atualizar o ranking no canal de ranking."""
    pontos = await obter_pontos()
    ranking = sorted(pontos.items(), key=lambda x: x[1], reverse=True)
    ranking_msg = "🏆 **Ranking de Pontuação** 🏆\n\n"

    for usuario, pontos_usuario in ranking:
        ranking_msg += f"**{usuario}**: {pontos_usuario} pontos\n"

    guild = discord.utils.get(bot.guilds, id=GUILD_ID)
    canal = discord.utils.get(guild.text_channels, id=CANAL_RANKING_ID)
    if canal:
        try:
            msg = await canal.send(ranking_msg)
        except Exception as e:
            print(f"Erro ao enviar mensagem no canal: {e}")

@bot.command()
async def adicionar_pontos(ctx, pontos: int, *, usuario: discord.Member):
    """Adicionar pontos a um usuário."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Você não tem permissão para adicionar pontos.")
        return

    pontos_atual = await obter_pontos()
    usuario_nome = usuario.name

    # Adicionar pontos ao usuário
    pontos_atual[usuario_nome] = pontos_atual.get(usuario_nome, 0) + pontos

    # Atualizar os pontos no canal
    await salvar_pontos()

    await ctx.send(f"✅ {pontos} pontos adicionados ao usuário **{usuario_nome}**!")

    # Verificar se o usuário atingiu 50 pontos e atribuir o cargo
    if pontos_atual[usuario_nome] >= 50:
        cargo_recruta = discord.utils.get(ctx.guild.roles, name="🍼 Recruta")
        if cargo_recruta:
            await usuario.add_roles(cargo_recruta)
            await ctx.send(f"🎉 O usuário **{usuario_nome}** atingiu 50 pontos e ganhou o cargo **🍼 Recruta**!")

    # Atualizar o ranking
    await atualizar_ranking()

@bot.command()
async def ranking(ctx):
    """Mostrar o ranking de pontos."""
    pontos = await obter_pontos()
    ranking = sorted(pontos.items(), key=lambda x: x[1], reverse=True)
    ranking_msg = "🏆 **Ranking de Pontuação** 🏆\n\n"

    for usuario, pontos_usuario in ranking:
        ranking_msg += f"**{usuario}**: {pontos_usuario} pontos\n"

    await ctx.send(ranking_msg)

@bot.event
async def on_ready():
    """Evento disparado quando o bot estiver pronto."""
    print(f"Bot conectado como {bot.user}")

bot.run(TOKEN)

from webserver import iniciar_web
import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import json
import os
import unicodedata
import time
import re
import aiohttp
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

# Bot command setup
bot = commands.Bot(command_prefix="!", intents=intents)

# Carregamento de arquivos JSON
def carregar_mortes():
    if not os.path.exists("mortes.json"):
        return {}
    with open("mortes.json", "r") as f:
        return json.load(f)

def salvar_mortes(mortes):
    with open("mortes.json", "w") as f:
        json.dump(mortes, f)

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

def normalizar_nome(nome):
    return unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII").lower().strip()

# Verificação de morte e status de personagens
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
    if not checar_mortes_ativo:
        return

    print("[DEBUG] Verificando mortes globais...")
    listas = carregar_listas()
    mortes_anteriores = carregar_mortes()
    canal = bot.get_channel(CANAL_MORTES_ID)

    nomes_monitorados = set(normalizar_nome(nome) for nomes in listas.values() for nome in nomes)

    url = "https://miracle74.com/?subtopic=latestdeaths"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()

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
                    continue

                print(f"[DEBUG] Nova morte detectada: {linha}")
                mortes_anteriores[nome_monitorado] = linha
                await canal.send(f"☠️ **{nome_monitorado} morreu!**\nMorte: {linha}")

    salvar_mortes(mortes_anteriores)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    checar_mortes_globais.start()

@bot.command()
async def addlist(ctx, *, nome_lista):
    listas = carregar_listas()

    if nome_lista in listas:
        await ctx.send(f"A lista **{nome_lista}** já existe.")
        return

    listas[nome_lista] = []
    salvar_listas(listas)
    await ctx.send(f"✅ Lista **{nome_lista}** criada com sucesso!")

@bot.command()
async def add(ctx, *, args):
    try:
        nome, lista = args.rsplit(" ", 1)
        lista = lista.strip()
    except ValueError:
        await ctx.send("❌ Formato incorreto. Use: `!add <nome_personagem> <nome_lista>`")
        return

    listas = carregar_listas()

    if lista not in listas:
        await ctx.send(f"❌ Lista **{lista}** não existe.")
        return

    if nome in listas[lista]:
        await ctx.send(f"🔁 O personagem **{nome}** já está na lista **{lista}**.")
        return

    listas[lista].append(nome)
    salvar_listas(listas)
    await ctx.send(f"✅ Personagem **{nome}** adicionado à lista **{lista}**.")

@bot.command()
async def removelist(ctx, *, nome_lista):
    listas = carregar_listas()

    if nome_lista not in listas:
        await ctx.send(f"❌ Lista **{nome_lista}** não encontrada.")
        return

    del listas[nome_lista]
    salvar_listas(listas)
    await ctx.send(f"🗑️ Lista **{nome_lista}** deletada com sucesso.")

@bot.command()
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

bot.run(TOKEN)

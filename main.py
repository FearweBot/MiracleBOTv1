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
import aiohttp  # no topo do seu arquivo
from dotenv import load_dotenv
from functools import wraps

iniciar_web()

checar_mortes_ativo = True  # Estado inicial: checar mortes está ativado

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))  # ID da guild (servidor)

CANAL_MORTES_ID = int(os.getenv("CANAL_MORTES_ID"))

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
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

def checar_permissao():
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            role = discord.utils.get(ctx.author.roles, name="list")
            if role is None:
                await ctx.send("❌ Você não tem permissão para usar este comando.")
                return
            return await func(ctx, *args, **kwargs)
        return wrapper
    return decorator

def carregar_mortes():
    if not os.path.exists("mortes.json"):
        return {}
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
    tabelas = soup.find_all("table", {"class": "TableContent"})
    for tabela in tabelas:
        titulo = tabela.find_previous("b")
        if titulo and "Deaths" in titulo.text:
            linhas = tabela.find_all("tr")[1:]
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
                if ultima_morte == linha:
                    continue
                mortes_anteriores[nome_monitorado] = linha
                await canal.send(f"☠️ **{nome_monitorado} morreu!**\nMorte: {linha}")

    salvar_mortes(mortes_anteriores)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    checar_status.start()
    checar_mortes_globais.start()

@bot.command()
@checar_permissao()
async def startdeaths(ctx):
    global checar_mortes_ativo
    if checar_mortes_ativo:
        await ctx.send("A checagem de mortes já está ativada.")
    else:
        checar_mortes_ativo = True
        checar_mortes_globais.start()
        await ctx.send("A checagem de mortes foi ativada.")

@bot.command()
@checar_permissao()
async def stopdeaths(ctx):
    global checar_mortes_ativo
    if not checar_mortes_ativo:
        await ctx.send("A checagem de mortes já está desativada.")
    else:
        checar_mortes_ativo = False
        checar_mortes_globais.stop()
        await ctx.send("A checagem de mortes foi desativada.")

# Continue aplicando @checar_permissao() a todos os outros comandos se desejar segurança completa

bot.run(TOKEN)

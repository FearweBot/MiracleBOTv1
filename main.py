from webserver import iniciar_web
import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import os
import unicodedata
import time
import re
import aiohttp
from dotenv import load_dotenv
from functools import wraps
import firebase_admin
from firebase_admin import credentials, firestore
import json

iniciar_web()

checar_mortes_ativo = False

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
CANAL_MORTES_ID = int(os.getenv("CANAL_MORTES_ID"))

# Inicializa o Firestore
firebase_creds = json.loads(os.getenv("FIREBASE_CREDENTIALS"))
cred = credentials.Certificate(firebase_creds)
firebase_admin.initialize_app(cred)
db = firestore.client()

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
    doc = db.collection("dados").document("mortes").get()
    return doc.to_dict() or {}

def salvar_mortes(mortes):
    db.collection("dados").document("mortes").set(mortes)

def normalizar_nome(nome):
    return unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII").lower().strip()

def carregar_listas():
    doc = db.collection("dados").document("listas").get()
    return doc.to_dict() or {}

def salvar_listas(dados):
    db.collection("dados").document("listas").set(dados)

def carregar_mensagens():
    doc = db.collection("dados").document("mensagens").get()
    return doc.to_dict() or {}

def salvar_mensagens(dados):
    db.collection("dados").document("mensagens").set(dados)

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

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    checar_status.start()
    checar_mortes_globais.start()

bot.run(TOKEN)

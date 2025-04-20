from webserver import iniciar_web
import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import unicodedata
import time
import re
import aiohttp  # no topo do seu arquivo
from dotenv import load_dotenv
from functools import wraps

# Configuração do Firebase
firebase_credentials = json.loads(os.getenv('FIREBASE_CREDENTIALS'))
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Função para obter dados das listas, mortes e mensagens do Firestore
def obter_dados_firestore(collection_name):
    collection_ref = db.collection(collection_name)
    docs = collection_ref.stream()
    return {doc.id: doc.to_dict() for doc in docs}

# Função para salvar os dados no Firestore
def salvar_dados_firestore(collection_name, dados):
    collection_ref = db.collection(collection_name)
    for key, value in dados.items():
        collection_ref.document(key).set(value)

iniciar_web()

checar_mortes_ativo = False  # Estado inicial: checar mortes está ativado

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

def normalizar_nome(nome):
    return unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII").lower().strip()

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

    listas = obter_dados_firestore('listas')
    mortes_anteriores = obter_dados_firestore('mortes')
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

    salvar_dados_firestore('mortes', mortes_anteriores)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    checar_status.start()
    checar_mortes_globais.start()

# Mantendo os comandos com as funções de integração com Firebase
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

@bot.command()
@checar_permissao()
async def addguild(ctx, link, *, lista):
    listas = obter_dados_firestore('listas')
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
                raw_nome = colunas[1].get_text(strip=True)
                nome = re.sub(r"\\s*\\(.*?\\)", "", raw_nome).strip()

                if nome and nome not in listas[lista]:
                    listas[lista].append(nome)
                    nomes_adicionados.append(nome)

        salvar_dados_firestore('listas', listas)
        await ctx.send(f"✅ {len(nomes_adicionados)} personagens adicionados à lista **{lista}**.")
    except Exception as e:
        await ctx.send(f"Erro ao adicionar guild: {e}")

@bot.command()
@checar_permissao()
async def addlist(ctx, *, nome_lista):
    guild = ctx.guild
    listas = obter_dados_firestore('listas')
    mensagens = obter_dados_firestore('mensagens')

    if nome_lista in listas:
        await ctx.send(f"A lista **{nome_lista}** já existe.")
        return

    canal = discord.utils.get(guild.text_channels, name=nome_lista.lower().replace(" ", "-"))
    if not canal:
        canal = await guild.create_text_channel(nome_lista.lower().replace(" ", "-"))

    listas[nome_lista] = []
    mensagens[nome_lista] = None
    salvar_dados_firestore('listas', listas)
    salvar_dados_firestore('mensagens', mensagens)
    await ctx.send(f"✅ Lista **{nome_lista}** criada com sucesso!")

@bot.command()
@checar_permissao()
async def removelist(ctx, *, nome_lista):
    listas = obter_dados_firestore('listas')
    mensagens = obter_dados_firestore('mensagens')

    if nome_lista not in listas:
        await ctx.send(f"❌ Lista **{nome_lista}** não encontrada.")
        return

    del listas[nome_lista]
    salvar_dados_firestore('listas', listas)

    if nome_lista in mensagens:
        del mensagens[nome_lista]
        salvar_dados_firestore('mensagens', mensagens)

    canal = discord.utils.get(ctx.guild.text_channels, name=nome_lista.lower().replace(" ", "-"))
    if canal:
        await canal.delete()

    await ctx.send(f"🗑️ Lista **{nome_lista}** e canal deletados com sucesso.")

# Continue adaptando os outros comandos para acessar o Firestore de forma similar.

bot.run(TOKEN)

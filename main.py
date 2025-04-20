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
from functools import wraps

iniciar_web()

checar_mortes_ativo = True  # Estado inicial: checar mortes está ativado

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))  # ID da guild (servidor)

CANAL_MORTES_ID = int(os.getenv("CANAL_MORTES_ID"))
CANAL_LOG_PONTOS_ID = 1363301544413368444  # Canal para log de pontos
CANAL_RANKING_ID = 1363152713365590187  # Canal para ranking

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
pontuacao_file = "pontuacao.json"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Função para verificar a permissão de admin
def checar_permissao():
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            role = discord.utils.get(ctx.author.roles, name="👑 Admin")
            if role is None:
                await ctx.send("❌ Você não tem permissão para usar este comando.")
                return
            return await func(ctx, *args, **kwargs)
        return wrapper
    return decorator

# Funções de gerenciamento de listas
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

def carregar_pontuacao():
    if not os.path.exists(pontuacao_file):
        return {}
    with open(pontuacao_file, "r") as f:
        return json.load(f)

def salvar_pontuacao(dados):
    with open(pontuacao_file, "w") as f:
        json.dump(dados, f)

# Funções para verificar status e mortes
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

# Comando para adicionar pontos
@bot.command()
@checar_permissao()
async def addpontos(ctx, pontos: int, *, usuarios: str):
    pontuacoes = carregar_pontuacao()
    usuarios = [user.strip() for user in usuarios.split(",")]

    canal_log = bot.get_channel(CANAL_LOG_PONTOS_ID)

    for usuario in usuarios:
        if usuario not in pontuacoes:
            pontuacoes[usuario] = 0
        pontuacoes[usuario] += pontos
        await canal_log.send(f"✅ {usuario} recebeu **{pontos} pontos**! Total: {pontuacoes[usuario]} pontos.")

        if pontuacoes[usuario] >= 50:
            guild = bot.get_guild(GUILD_ID)
            membro = discord.utils.get(guild.members, name=usuario)
            if membro:
                role = discord.utils.get(guild.roles, name="🍼 Recruta")
                if role and role not in membro.roles:
                    await membro.add_roles(role)
                    await canal_log.send(f"🎉 {usuario} atingiu 50 pontos e agora é um **🍼 Recruta**!")

    salvar_pontuacao(pontuacoes)

# Comando para mostrar ranking
@bot.command()
async def ranking(ctx):
    pontuacoes = carregar_pontuacao()
    ranking = sorted(pontuacoes.items(), key=lambda x: x[1], reverse=True)

    canal_ranking = bot.get_channel(CANAL_RANKING_ID)

    ranking_msg = "**🏆 Ranking de Pontuação:**\n\n"
    for i, (usuario, pontos) in enumerate(ranking, start=1):
        ranking_msg += f"{i}. **{usuario}**: {pontos} pontos\n"

    await canal_ranking.send(ranking_msg)

# Adicionar a função de monitoramento de status e mortes
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

# Inicializar o bot
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    checar_status.start()

bot.run(TOKEN)

import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import json
import os
import unicodedata
import time
import re
from dotenv import load_dotenv

# Variável global para armazenar o tempo da última verificação
ultima_atualizacao = time.time()

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

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CANAL_ID = int(os.getenv("CANAL_ID", "0"))
CANAL_MORTES_ID = int(os.getenv("CANAL_MORTES_ID", "0"))

personagens_file = "personagens.json"
mensagem_id_file = "mensagem_id.txt"
mortes_file = "mortes.json"
config_file = "config.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def carregar_personagens():
    if not os.path.exists(personagens_file):
        return []
    with open(personagens_file, "r") as f:
        return json.load(f)

def salvar_personagens(personagens):
    with open(personagens_file, "w") as f:
        json.dump(personagens, f)

def carregar_mortes():
    if not os.path.exists(mortes_file):
        return {}
    with open(mortes_file, "r") as f:
        return json.load(f)

def salvar_mortes(mortes):
    with open(mortes_file, "w") as f:
        json.dump(mortes, f)

def carregar_config():
    if not os.path.exists(config_file):
        return {"verificar_mortes": False}
    with open(config_file, "r") as f:
        return json.load(f)

def salvar_config(config):
    with open(config_file, "w") as f:
        json.dump(config, f)

def normalizar_nome(nome):
    return unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII").lower().strip()

def verificar_status(nome):
    url = "https://miracle74.com/?subtopic=whoisonline"
    resposta = requests.get(url)
    soup = BeautifulSoup(resposta.text, "html.parser")

    tabelas = soup.find_all("table", {"class": "TableContent"})
    personagens_info = []

    for tabela in tabelas:
        linhas = tabela.find_all("tr")[1:]
        for linha in linhas:
            colunas = linha.find_all("td")
            if colunas and len(colunas) >= 4:
                nome_completo = colunas[1].find("a").text.strip() if colunas[1].find("a") else ""
                level = colunas[2].text.strip()
                vocacao = colunas[3].text.strip()

                match = re.match(r"([a-zA-ZÀ-ÿ\s]+)", nome_completo)
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
            vocacao_abreviada = VOCACOES.get(personagem["vocacao"], personagem["vocacao"])
            return f"{vocacao_abreviada} - {personagem['level']} 🟢"

    return None

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    checar_status.start()

@tasks.loop(seconds=30)
async def checar_status():
    personagens = carregar_personagens()
    mortes_anteriores = carregar_mortes()
    config = carregar_config()
    status_msg = "**📋 Status dos personagens monitorados:**\n\n"
    canal_status = bot.get_channel(CANAL_ID)
    canal_mortes = bot.get_channel(CANAL_MORTES_ID)
    resultado_geral = []  # Lista para armazenar status de todos os personagens

    for nome in personagens:
        status = verificar_status(nome)
        if status:
            match = re.search(r"(\d+)", status)
            level = int(match.group(1)) if match else 0
            resultado_geral.append({
                "nome": nome,
                "status": status,
                "level": level
            })

        if config.get("verificar_mortes"):
            ultima_morte = verificar_ultima_morte(nome)
            if ultima_morte and mortes_anteriores.get(nome) != ultima_morte:
                mortes_anteriores[nome] = ultima_morte
                await canal_mortes.send(f"☠️ **{nome} morreu!**\n{ultima_morte}")

    # Ordenar por level (maior para menor)
    resultado_ordenado = sorted(resultado_geral, key=lambda x: x["level"], reverse=True)

    if resultado_ordenado:
        status_msg += "\n".join(f"**{item['nome']}**: {item['status']}" for item in resultado_ordenado)
    else:
        status_msg = "**📋 Status dos personagens monitorados:**\nNenhum personagem online no momento."


    salvar_mortes(mortes_anteriores)

    if not os.path.exists(mensagem_id_file):
        mensagem = await canal_status.send(status_msg)
        with open(mensagem_id_file, "w") as f:
            f.write(str(mensagem.id))
    else:
        with open(mensagem_id_file, "r") as f:
            msg_id = f.read().strip()
        try:
            mensagem = await canal_status.fetch_message(int(msg_id))
            await mensagem.edit(content=status_msg)
        except:
            mensagem = await canal_status.send(status_msg)
            with open(mensagem_id_file, "w") as f:
                f.write(str(mensagem.id))

@bot.command(name="add")
async def adicionar_personagem(ctx, *, nome: str):
    personagens = carregar_personagens()
    nome_normalizado = nome.strip()
    if nome_normalizado in personagens:
        await ctx.send(f"⚠️ O personagem **{nome_normalizado}** já está sendo monitorado.")
        return
    personagens.append(nome_normalizado)
    salvar_personagens(personagens)
    await ctx.send(f"✅ Personagem **{nome_normalizado}** adicionado à lista de monitoramento.")

@bot.command(name="remove")
async def remover_personagem(ctx, *, nome: str):
    personagens = carregar_personagens()
    nome_normalizado = nome.strip()
    if nome_normalizado not in personagens:
        await ctx.send(f"⚠️ O personagem **{nome_normalizado}** não está na lista.")
        return
    personagens.remove(nome_normalizado)
    salvar_personagens(personagens)
    await ctx.send(f"🗑️ Personagem **{nome_normalizado}** removido da lista.")

@bot.command(name="list")
async def listar_personagens(ctx):
    personagens = carregar_personagens()
    if not personagens:
        await ctx.send("📭 Nenhum personagem está sendo monitorado no momento.")
    else:
        nomes = "\n".join([f"• {nome}" for nome in personagens])
        await ctx.send(f"📋 Lista de personagens monitorados:\n{nomes}")

bot.run(TOKEN)

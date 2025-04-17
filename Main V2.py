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

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))  # ID da guild (servidor)

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
                nome_completo = colunas[1].find("a").text.strip()
                level = colunas[2].text.strip()
                vocacao = colunas[3].text.strip()
                match = re.match(r"([a-zA-ZÀ-ÿ\s'\-]+)", nome_completo)
                if match:
                    nome_personagem = match.group(1).strip()
                    personagens_info.append({
                        "nome": nome_personagem,
                        "level": level,
                        "vocacao": vocacao
                    })

    nome_normalizado = normalizar_nome(nome)
    for p in personagens_info:
        if normalizar_nome(p["nome"]) == nome_normalizado:
            v = VOCACOES.get(p["vocacao"], p["vocacao"])
            return f"{v} - {p['level']} 🟢"
    return None

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    checar_status.start()

@bot.command()
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
            status = verificar_status(nome)
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

bot.run(TOKEN)

import re
 import aiohttp  # no topo do seu arquivo
 from dotenv import load_dotenv
 from functools import wraps
 
 iniciar_web()
 
 @@ -39,12 +40,25 @@
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
         return []
         return {}
     with open("mortes.json", "r") as f:
         return json.load(f)
 
 @@ -82,13 +96,11 @@ async def verificar_ultima_morte(nome):
             html = await response.text()
 
     soup = BeautifulSoup(html, "html.parser")
 
     # Procura por todas as tabelas
     tabelas = soup.find_all("table", {"class": "TableContent"})
     for tabela in tabelas:
         titulo = tabela.find_previous("b")
         if titulo and "Deaths" in titulo.text:
             linhas = tabela.find_all("tr")[1:]  # Ignora o header
             linhas = tabela.find_all("tr")[1:]
             if not linhas:
                 return None
             colunas = linhas[0].find_all("td")
 @@ -115,7 +127,6 @@ async def verificar_status(nome):
                 nome_completo = colunas[1].find("a").text.strip()
                 level = colunas[2].text.strip()
                 vocacao = colunas[3].text.strip()
 
                 match = re.match(r"([a-zA-ZÀ-ÿ\s'\-]+)", nome_completo)
                 if match:
                     nome_personagem = match.group(1).strip()
 @@ -131,28 +142,24 @@ async def verificar_status(nome):
         if normalizar_nome(personagem["nome"]) == nome_normalizado:
             voc_abrev = VOCACOES.get(personagem["vocacao"], personagem["vocacao"])
             return f"{voc_abrev} - {personagem['level']} 🟢"
     
     return None
 
 @tasks.loop(seconds=30)
 async def checar_mortes_globais():
     if not checar_mortes_ativo:  # Se a checagem de mortes estiver desativada, retorna imediatamente
     if not checar_mortes_ativo:
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
 
 @@ -164,13 +171,8 @@ async def checar_mortes_globais():
         for nome_monitorado in nomes_monitorados:
             if nome_monitorado in normalizar_nome(linha):
                 ultima_morte = mortes_anteriores.get(nome_monitorado)
                 
                 # Se a morte já foi registrada anteriormente, ignora
                 if ultima_morte == linha:
                     print(f"[DEBUG] Morte já registrada para {nome_monitorado}: {linha}")
                     continue  # Ignora e passa para a próxima linha de morte
 
                 print(f"[DEBUG] Nova morte detectada: {linha}")
                     continue
                 mortes_anteriores[nome_monitorado] = linha
                 await canal.send(f"☠️ **{nome_monitorado} morreu!**\nMorte: {linha}")
 
 @@ -182,7 +184,6 @@ async def on_ready():
     checar_status.start()
     checar_mortes_globais.start()
 
 # (Comandos do bot... os comandos restantes aqui sem alterações)
 @bot.command()
 @checar_permissao()
 async def startdeaths(ctx):
 @@ -191,7 +192,7 @@ async def startdeaths(ctx):
         await ctx.send("A checagem de mortes já está ativada.")
     else:
         checar_mortes_ativo = True
         checar_mortes_globais.start()  # Inicia o loop da checagem de mortes
         checar_mortes_globais.start()
         await ctx.send("A checagem de mortes foi ativada.")
 
 @bot.command()
 @@ -202,10 +203,10 @@ async def stopdeaths(ctx):
         await ctx.send("A checagem de mortes já está desativada.")
     else:
         checar_mortes_ativo = False
         checar_mortes_globais.stop()  # Para o loop da checagem de mortes
         checar_mortes_globais.stop()
         await ctx.send("A checagem de mortes foi desativada.")
 
 
 # Continue aplicando @checar_permissao() a todos os outros comandos se desejar segurança completa
 @bot.command()
 @checar_permissao()
 async def addguild(ctx, link, *, lista):
 @@ -402,5 +403,5 @@ async def checar_status():
                 salvar_mensagens(mensagens)
         except Exception as e:
             print(f"[ERRO]: {e}")
 
bot.run(TOKEN)

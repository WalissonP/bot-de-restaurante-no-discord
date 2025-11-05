import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- ARQUIVOS DE IMAGENS ---
IMAGENS = {
    "lanches": "lanches.png",
    "pizzas": "pizzas.png",
    "porcoes": "porcoes.png",
    "bebidas": "bebidas.png"
}

# --- ITENS DE CADA CATEGORIA ---
ITENS = {
    "lanches": ["Hambúrguer", "X-Bacon", "X-Burguer", "X-Calabresa", "X-Egg", "MC bacon"],
    "pizzas": ["Pepperoni", "Portuguesa", "Napolitana", "Tropical", "Calabresa"],
    "porcoes": ["Mandioca", "Batata ou Polenta", "Croquete", "Pastel de Jabá", "Torresmo", "Frango c/ Polenta"],
    "bebidas": ["Água", "Refrigerante", "Sucos", "Cerveja", "Chopp", "Café", "Capuccino"]
}

usuarios_atendidos = set()
fluxo_pedido = {}  # Armazena progresso do pedido do usuário


# =========================================================
# BOTÕES DAS CATEGORIAS
# =========================================================
class CategoriaView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Lanches", style=discord.ButtonStyle.primary)
    async def lanches(self, interaction, button):
        await enviar_cardapio_categoria(interaction, "lanches")

    @discord.ui.button(label="Pizzas", style=discord.ButtonStyle.primary)
    async def pizzas(self, interaction, button):
        await enviar_cardapio_categoria(interaction, "pizzas")

    @discord.ui.button(label="Porções", style=discord.ButtonStyle.primary)
    async def porcoes(self, interaction, button):
        await enviar_cardapio_categoria(interaction, "porcoes")

    @discord.ui.button(label="Bebidas", style=discord.ButtonStyle.primary)
    async def bebidas(self, interaction, button):
        await enviar_cardapio_categoria(interaction, "bebidas")


# =========================================================
# ENVIA IMAGEM + BOTÕES DOS ITENS
# =========================================================
async def enviar_cardapio_categoria(interaction, categoria):

    file = discord.File(IMAGENS[categoria])
    await interaction.response.send_message(file=file)

    view = View()

    # Criar botão para cada item
    for item in ITENS[categoria]:
        button = Button(label=item, style=discord.ButtonStyle.success)

        async def handler(inter, item_escolhido=item):
            await iniciar_fluxo_pedido(inter, item_escolhido)

        button.callback = handler
        view.add_item(button)

    await interaction.followup.send(
        f"Escolha uma opção de **{categoria.capitalize()}**:",
        view=view
    )


# =========================================================
# INICIAR FLUXO DE PEDIDO
# =========================================================
async def iniciar_fluxo_pedido(interaction, item):
    user_id = interaction.user.id

    fluxo_pedido[user_id] = {
        "item": item,
        "etapa": "nome",
        "nome": "",
        "endereco": "",
        "pagamento": ""
    }

    await interaction.response.send_message(
        f"✅ Você escolheu **{item}**.\n\n"
        "Vamos finalizar o pedido!\n\n"
        "**Digite seu nome:**"
    )


# =========================================================
# CAPTURAR MENSAGENS DO USUÁRIO (NOME > ENDEREÇO > PAGAMENTO)
# =========================================================
@bot.event
async def on_message(message):

    if message.author == bot.user:
        return

    user_id = message.author.id

    # Se não está no fluxo de pedido
    if user_id not in fluxo_pedido:

        # Primeira mensagem
        if user_id not in usuarios_atendidos:
            usuarios_atendidos.add(user_id)

            await message.channel.send(
                f"Olá **{message.author.mention}**, seja bem-vindo! 😄\n"
                "Escolha uma categoria abaixo para ver o cardápio.\n\n"
                "Para ver novamente, digite **!cardapio**",
                view=CategoriaView()
            )
            return

        return await bot.process_commands(message)

    # Usuário está no fluxo do pedido
    etapa = fluxo_pedido[user_id]["etapa"]

    if etapa == "nome":
        fluxo_pedido[user_id]["nome"] = message.content
        fluxo_pedido[user_id]["etapa"] = "endereco"

        await message.channel.send("✅ Nome anotado!\nAgora digite **seu endereço completo**:")
        return

    if etapa == "endereco":
        fluxo_pedido[user_id]["endereco"] = message.content
        fluxo_pedido[user_id]["etapa"] = "pagamento"

        await message.channel.send(
            "✅ Endereço registrado!\n"
            "Agora escolha a forma de pagamento:\n\n"
            "**Digite:**\n• Dinheiro\n• Pix\n• Cartão"
        )
        return

    if etapa == "pagamento":
        fluxo_pedido[user_id]["pagamento"] = message.content
        fluxo_pedido[user_id]["etapa"] = "finalizado"

        item = fluxo_pedido[user_id]["item"]
        nome = fluxo_pedido[user_id]["nome"]
        end = fluxo_pedido[user_id]["endereco"]
        pag = fluxo_pedido[user_id]["pagamento"]

        await message.channel.send(
            "✅ **PEDIDO FINALIZADO!**\n\n"
            f"🍽 **Item:** {item}\n"
            f"👤 **Nome:** {nome}\n"
            f"🏠 **Endereço:** {end}\n"
            f"💳 **Pagamento:** {pag}\n\n"
            "Seu pedido está sendo preparado! ✅"
        )

        fluxo_pedido.pop(user_id)
        return


# =========================================================
# COMANDO PARA VER O CARDÁPIO
# =========================================================
@bot.command()
async def cardapio(ctx):
    await ctx.send("Escolha uma categoria:", view=CategoriaView())


# =========================================================
# START
# =========================================================
bot.run(TOKEN)

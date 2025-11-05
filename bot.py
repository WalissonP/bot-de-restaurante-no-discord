import discord
from discord.ext import commands

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
    "porcoes": ["Mandioca", "Batata ou Polenta", "Croquete Mandioca c/ jabá, Presunto e Mussarela, Provolone ou c/ Picante", "Pastel de Jabá c/ Mussarela", "Torresmo", "Frango c/ Polenta, Batata ou Mandioca"],
    "bebidas": ["Água", "Refrigerante", "Sucos", "Cerveja", "Chopp", "Café", "Capuccino"]
}

# --- REGISTRO DE QUEM JÁ RECEBEU SAUDAÇÃO ---
usuarios_atendidos = set()


class CategoriaView(discord.ui.View):
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


async def enviar_cardapio_categoria(interaction, categoria):
    """Envia a imagem da categoria + botões dos itens"""

    # Envia a imagem
    file = discord.File(IMAGENS[categoria])
    await interaction.response.send_message(file=file)

    # Cria botões dinamicamente
    view = discord.ui.View()
    for item in ITENS[categoria]:
        view.add_item(discord.ui.Button(label=item, style=discord.ButtonStyle.success))

    await interaction.followup.send(f"Escolha uma opção de **{categoria.capitalize()}**:", view=view)


# --- PRIMEIRA MENSAGEM DO CLIENTE ---
@bot.event
async def on_message(message: discord.Message):

    if message.author == bot.user:
        return

    # Apenas primeira mensagem
    if message.author.id not in usuarios_atendidos:
        usuarios_atendidos.add(message.author.id)

        await message.channel.send(
            f"Olá **{message.author.mention}**, seja bem-vindo! 😄\n"
            "Escolha uma categoria abaixo para ver o cardápio.\n\n"
            "Para ver novamente, digite **!cardapio**",
            view=CategoriaView()
        )
        return

    # Permite comandos como !cardapio
    await bot.process_commands(message)


# --- COMANDO PARA VER O CARDÁPIO NOVAMENTE ---
@bot.command()
async def cardapio(ctx):
    await ctx.send("Escolha uma categoria:", view=CategoriaView())


# --- TOKEN ---
bot.run("MTQzMzUxMzA5MzYzNTI0NDA5Mg.GrEn4B.DdUVPl4CcWUBrcelFpNEAcTKvQVRELJ3rBSsgk")

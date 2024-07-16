import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
import os
import re
from openai import OpenAI

client = OpenAI(
  api_key="<OpenAI API Key>",
)

# Directory to save feedback files
FEEDBACK_DIR = "feedback"

# Create feedback directory if it doesn't exist
os.makedirs(FEEDBACK_DIR, exist_ok=True)

intents = discord.Intents.default()
intents.message_content=True
bot = commands.Bot(command_prefix='!', intents=intents)

# Define the discord role required to create feedback forms
REQUIRED_ROLE = "Dev"

class FeedbackModal(Modal):
    def __init__(self, topic):
        super().__init__(title="Feedback")
        self.topic = topic
        self.add_item(TextInput(label="Your Feedback", style=discord.TextStyle.long, placeholder="Enter your feedback here..."))

    async def on_submit(self, interaction: discord.Interaction):
        feedback = self.children[0].value
        file_path = os.path.join(FEEDBACK_DIR, f"{self.topic}.txt")
        with open(file_path, "a") as file:
            file.write(f"{feedback}\n\n")
        await interaction.response.send_message(f"Thank you for your feedback, it has been kept anonymous!", ephemeral=True)

class CreateFeedbackFormModal(Modal):
    def __init__(self):
        super().__init__(title="Create Feedback Form")
        self.add_item(TextInput(label="Feedback Topic", placeholder="Enter the topic for the feedback..."))
        self.add_item(TextInput(label="Description", placeholder="Enter a description for the feedback...", style=discord.TextStyle.long))
        self.add_item(TextInput(label="Channel ID", placeholder="Enter the channel ID..."))

    async def on_submit(self, interaction: discord.Interaction):
        topic = self.children[0].value
        description = self.children[1].value
        channel_id = int(self.children[2].value)
        target_channel = interaction.guild.get_channel(channel_id)
        
        if target_channel is None:
            await interaction.response.send_message("Invalid channel ID. Please try again.", ephemeral=True)
            return
        
        embed = discord.Embed(title=topic, description=description, color=discord.Color.blue())
        embed.set_footer(text="All Feedback is Anonymous", icon_url="https://images-wixmp-ed30a86b8c4ca887773594c2.wixmp.com/f/39ac6b8e-c8c9-4d20-a781-2b36215bf34a/d2xcd3j-64166fe4-f8d0-4316-a440-6208cbe0180d.gif?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1cm46YXBwOjdlMGQxODg5ODIyNjQzNzNhNWYwZDQxNWVhMGQyNmUwIiwiaXNzIjoidXJuOmFwcDo3ZTBkMTg4OTgyMjY0MzczYTVmMGQ0MTVlYTBkMjZlMCIsIm9iaiI6W1t7InBhdGgiOiJcL2ZcLzM5YWM2YjhlLWM4YzktNGQyMC1hNzgxLTJiMzYyMTViZjM0YVwvZDJ4Y2Qzai02NDE2NmZlNC1mOGQwLTQzMTYtYTQ0MC02MjA4Y2JlMDE4MGQuZ2lmIn1dXSwiYXVkIjpbInVybjpzZXJ2aWNlOmZpbGUuZG93bmxvYWQiXX0.tUV_1C5sWL4lY1FM8oJLFCCvEUBhuT0bbml1ZHyqPGg")
        button = Button(label="Give Feedback", style=discord.ButtonStyle.primary)

        async def button_callback(interaction):
            modal = FeedbackModal(topic)
            await interaction.response.send_modal(modal)

        button.callback = button_callback
        view = View(timeout=None)
        view.add_item(button)
        
        await target_channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"Feedback form created successfully in <#{target_channel.id}>", ephemeral=True)

class CreateFeedbackButton(View):
    @discord.ui.button(label="Create Feedback Form", style=discord.ButtonStyle.primary)
    async def create_feedback_form_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CreateFeedbackFormModal()
        await interaction.response.send_modal(modal)

@bot.command(name="feedback")
# @commands.has_role(REQUIRED_ROLE)
async def create_feedback(ctx):
    try:
        if REQUIRED_ROLE not in [role.name for role in ctx.author.roles]:
            await ctx.send("You do not have the required role to create a feedback form, you need <@&1203896588766937119>.")
            return

        view = CreateFeedbackButton(timeout=None)
        message = await ctx.send("Click the button below to create a new feedback form in a specific channel by ID.", view=view)
        
        # Dictionary to hold the state of the buttons
        button_states = {}

        for item in view.children:
            if isinstance(item, discord.ui.Button):
                # Save the state of the button
                if message.id not in button_states:
                    button_states[message.id] = {}
                button_states[message.id][item.label] = (item.disabled, item.style.value)

        # Write the button states to a file
        with open('feedback_states.json', 'w') as f:
            json.dump(button_states, f)
    except Exception as e:
        await ctx.send(f"Failed to create feedback form: {e}")

@bot.command(name="summarize_feedback")
@commands.has_role(REQUIRED_ROLE)
async def summarize_feedback(ctx, topic: str):
    try:
        print(f"Topic file: {topic}.txt")
        file_path = os.path.join(FEEDBACK_DIR, f"{topic}.txt")
        if not os.path.exists(file_path):
            await ctx.send(f"No feedback found for topic '{topic}'.")
            return

        with open(file_path, "r") as file:
            feedback_content = file.read()

        if not feedback_content.strip():
            await ctx.send(f"No feedback found for topic '{topic}'.")
            return

        # Check if input text is too short
        if len(feedback_content) < 10:
            await ctx.send("Feedback content is too short to summarize.")
            return
        
        # Summarize feedback using GPT-3.5
        prompt = (f"Summarize the following feedback about '{topic}':\n"
                  f"{feedback_content}")

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that takes all the different feedback and summarizes it into bullet points to easily understand the common themes and pain points that users are feeling."},
                {"role": "user", "content": prompt}
            ]
        )
        # print(response.choices[0].message.content)

        summary = response.choices[0].message.content.strip()

        # Clean up the summary text
        summary = re.sub(r'\.\.\.', '.', summary)
        summary = re.sub(r'\.\.', '.', summary)

        await ctx.send(f'Summary for feedback on Topic `{topic}`:\n```{summary}```')
    except Exception as e:
        await ctx.send(f"Failed to summarize feedback: {e}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

bot.run('<Bot Token>')

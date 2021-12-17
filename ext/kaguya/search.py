from datetime import datetime

import discord
from discord.ext import commands
from typing import List

class Select(discord.ui.Select['Paginator']):

	def __init__(self, options: List[discord.SelectOption]) -> None:
		super().__init__(placeholder="Jump to page...", min_values=1, max_values=1, options=options, row=1)

	async def callback(self, interaction: discord.Interaction):
		assert self.view is not None
		await self.view.process_callback(self, interaction)

class Paginator(discord.ui.View):

	children: List[discord.ui.Button]

	def __init__(self, ctx ,embeds: List[discord.Embed]):
		super().__init__(timeout=300.0)
		self.ctx = ctx
		self.embeds: List[discord.Embed] = embeds
		self.embed_pos = 0
		self.max = len(embeds)

		for i, embed in enumerate(self.embeds):
			embed.set_footer(text=f"{i + 1}/{self.max}")
			embed.timestamp = discord.utils.utcnow()

		select_options = [discord.SelectOption(label=f"{i+1}", value=str(i)) for i in range(self.max)]
		if self.max < 25:
			self.add_item(Select(select_options))
		# Well due to this we can't have more than 25 pages, so fuck selects


	async def on_timeout(self) -> None:
		return await super().on_timeout()

	async def interaction_check(self, interaction: discord.Interaction) -> bool:
		assert interaction.user is not None
		return interaction.user.id == self.ctx.author.id

	@discord.ui.button(emoji="\U000023ee", style=discord.ButtonStyle.primary)
	async def forward_start(self, button: discord.ui.Button, interaction: discord.Interaction):
		self.embed_pos = 0
		await interaction.response.edit_message(embed=self.embeds[0])

	
	@discord.ui.button(emoji="\U000023ea", style=discord.ButtonStyle.primary)
	async def backward_next(self, button: discord.ui.Button, interaction: discord.Interaction):
		if self.embed_pos - 1 < 0:
			return await interaction.response.send_message("uh- that's the first page.", ephemeral=True)
		self.embed_pos -= 1
		await interaction.response.edit_message(embed=self.embeds[self.embed_pos])

	@discord.ui.button(emoji="\U000023f9", style=discord.ButtonStyle.primary)
	async def stop_button(self, button: discord.ui.Button, interaction: discord.Interaction):
		for button in self.children:
			button.disabled = True
		await interaction.message.delete()
		self.stop()

	@discord.ui.button(emoji="\U000023e9", style=discord.ButtonStyle.primary)
	async def forward_next(self, button: discord.ui.Button, interaction: discord.Interaction):
		if self.embed_pos + 1 >= self.max:
			return await interaction.response.send_message("That's actually the last page lol.", ephemeral=True)
		self.embed_pos += 1
		await interaction.response.edit_message(embed=self.embeds[self.embed_pos])

	@discord.ui.button(emoji="\U000023ed", style=discord.ButtonStyle.primary)
	async def backward_end(self, button: discord.ui.Button, interaction: discord.Interaction):
		self.embed_pos = self.max - 1
		await interaction.response.edit_message(embed=self.embeds[self.embed_pos])

	async def process_callback(self,select: discord.ui.Select, interaction: discord.Interaction):
		assert interaction.data is not None
		opt: int = int(interaction.data["values"][0]) #type: ignore
		await interaction.response.edit_message(embed=self.embeds[opt])


class Search(commands.Cog):
	'''Search the manga.'''

	def __init__(self, bot : commands.AutoShardedBot):
		self.bot = bot
	
	async def search_in_manga(self, text : str) -> dict:
		page = 'https://guya.moe/api/search_index/Kaguya-Wants-To-Be-Confessed-To/'
		data = {'searchQuery' : text}
		async with self.bot.session.post(page, data= data) as resp:
			return await resp.json()

	def pick_common_entries(self, data : dict) -> dict:
		dicts= [list(val.values())[0] for val in data.values()]	
		keys = set.intersection(*tuple(set(d.keys()) for d in dicts))

		results = {}
		for key in keys:
			l = []
			for d in dicts:
				l.append(d[key])

			c = self.onlycommon(l)
			if c is not None:
				results[key] = c

		return results

	def onlycommon(self, lists: list) -> list:
		if len(lists) == 1:
			return lists[0]
		s = list(set(lists[0]).intersection(*lists))
		
		if s:
			return s
		return None

	def format_to_line(self, chapter : str, pages : List[int] ) -> str:
		string = f'`Ch. {chapter.replace("-" , ".")}` | Pages: '
		string+= ', '.join([f'[{page}](https://guya.moe/{chapter}/{page})' for page in pages])
		return string

	def prepare_for_paginator(self, lines: List[str]) -> List[list]:
		groups= [[]]
		i = 0
		for line in lines:
			if len(''.join(groups[i])) < 1000:
				groups[i].append(line)
				continue

			groups.append([])
			i += 1
			groups[i].append(line)

		return groups

	@commands.command(name='search', aliases= ['searchtext'])
	async def _search(self, ctx: commands.Context, *, text: str):
		'''
		Search the whole manga for a certain piece of text!
		This is just `guya.moe`'s search api, implemented and formatted for discord.

		Please note that this search is extremely inaccurate in certain cases.
		The api actually provides invidiual search results for each word if your query is multi-worded.  The final results are provided by me crossmatching those results in a number of ways.
		Due to this and how the api provides the results, there's no way to tell if your query (if multi-worded) is literally in the page or the words of the query are in different parts of the page text. 
		For example, searching "hey there" will assume that "hey, go there" is a valid result.
		Along with that, there might be some bugs with my crossmatching, producing invalid results.


		**Examples:**
		`search shinomiya`
		`search never gonna give you up`
		'''

		await ctx.trigger_typing() # Tends to take some time.
		result = (await self.search_in_manga(text))

		if not result:
			return await ctx.send('Nothing found :(')
		
		try:
			if len(text.split()) > 1:
				data= self.pick_common_entries(result)
			else:
				data= list(result[text].values())[0] # We'll only consider the first result.
		except IndexError:
			return await ctx.send('Ran into an error, sorry.')

		if not data:
			return await ctx.send('Nothing found :(')

		chapters = [int(x) if x.is_integer() else x 
					for x in sorted([float(i.replace('-','.')) 
					for i in data])]

		formatted_chapters = [str(c).replace('.','-') for c in chapters]

		lines= [self.format_to_line(formatted_chapters[c], data[formatted_chapters[c]])
				for c in range(len(formatted_chapters))]

		groups = self.prepare_for_paginator(lines)

		embeds = []
		for group in groups:
			desc = '\n'.join([line for line in group])
			embed = discord.Embed(title= f'Search results for "{text}" in Kaguya-sama main series',
									description= desc,
									color= ctx.me.color)

			embeds.append(embed)

		if len(embeds) == 1:
			# No need for paginator
			return await ctx.send(embed= embeds[0])

		paginator = Paginator(ctx, embeds)
		return await ctx.send(embed=embeds[0], view= paginator)


def setup(bot):
	bot.add_cog(Search(bot))



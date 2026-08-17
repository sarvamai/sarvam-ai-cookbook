import { Telegraf, session } from "telegraf";
import { config } from "dotenv";
import connectToDatabase from "./db.ts";
import type { InputFile } from "telegraf/types";
import Users from "./models/Users.ts";
import { SarvamAIClient } from "sarvamai";
import { message } from "telegraf/filters";
import Conversations from "./models/Conversations.ts";
import type { MyContext } from "./context.ts";
import errorHandler from "./middlewares/errorHandler.ts";
import telegramifyMarkdown from "telegramify-markdown";

config();
connectToDatabase();

const BOT_TOKEN = process.env.BOT_TOKEN;
const SARVAM_API_KEY = process.env.SARVAM_API_KEY;

// @ts-expect-error
const client = new SarvamAIClient({
	apiSubscriptionKey: SARVAM_API_KEY
});

const emoji = ()=>{
	const emojis = ["👍", "❤", "🔥", "🥰", "👏", "🎉", "🤩", "👌", "😍", "❤‍🔥", "⚡","👀", "😇", "✍", "🗿", "🆒", "😎"];
	const index = Math.round(Math.random()*10) % emojis.length;
	return emojis[index];
}

// @ts-expect-error
const bot = new Telegraf<MyContext>(BOT_TOKEN);

bot.use(session({
	defaultSession: ()=>({ chatId: crypto.randomUUID() })
}));

const $bannerImage: InputFile = { source: "./assets/banner.png", filename: "sarvam.png" }

bot.start(async (ctx)=>{
	const user = await Users.findOne({ userId: ctx.from.id });
	if(!user){
		// @ts-expect-error
		await Users.create({ name: ctx.from.first_name, userId: ctx.from.id, username: ctx.from.username });
	}
	await ctx.replyWithPhoto($bannerImage, {
		caption: "Welcome to Indus AI. Indus is a Conversational AI Model developed by Sarvam AI.\n\nClick the New Chat Button to continue",
		reply_markup: {
			keyboard: [
				[{ text: "New Chat" }]
			],
			is_persistent: true,
			resize_keyboard: true
		}
	});
});

bot.command("info", async (ctx)=>{
	const inlineKeyboard = [
		[{ text: "Sarvam AI Website", url: "https://sarvam.ai/" }],
		[{ text: "TelegrafJS", url: "https://github.com/telegraf/telegraf" }]
	];
	await ctx.reply(`Indus AI Bot is a Telegram Implementation of the Conversational Model Indus by Sarvam AI.\nThis is an unofficial bot\nResources used: Sarvam AI API for Chat Completion, TelegrafJS for Telegram Bot Framework.`, {
		reply_markup: {
			inline_keyboard: inlineKeyboard
		}
	});
});

bot.on("inline_query", async (ctx)=>{
	const query = ctx.inlineQuery;
	const queryText = query.query;
	const response = await client.chat.completions({
		messages: [
			{
				role: "user",
				content: queryText	
			}
		]
	});
	await ctx.telegram.answerInlineQuery(query.id, [{
		type: "article",
		description: response.choices[0].message.content.slice(0, 10) + "...",
		title: "Indus",
		id: "1",
		input_message_content: {
			message_text: telegramifyMarkdown(response.choices[0].message.content),
			parse_mode: "MarkdownV2"
		}
	}]);
});

bot.on(message("text"), async (ctx)=>{
	const message = ctx.message.text;
	const msg = ctx.message;
	let chatId = ctx.session.chatId;
	if(message === "New Chat"){
		await ctx.deleteMessage(msg.message_id);
		chatId = crypto.randomUUID();
		ctx.session.chatId = chatId;
		await ctx.reply("[+] New Chat Context Created! Start Chatting!");
		return;
	}
	// @ts-ignore
	await ctx.react(emoji());
	const userId = ctx.from.id;
	const del = await ctx.reply("Please Wait...");
	await Conversations.create({ chatId, userId, content: JSON.stringify(message), role: "user" });
	const wholeConvo = await Conversations.find({ userId, chatId }).sort("sendingTime").select("role content");
	const response = await client.chat.completions({
		messages: wholeConvo
	});
	await ctx.deleteMessage(del.message_id);
	// @ts-expect-error
	await ctx.reply(telegramifyMarkdown(response.choices[0].message.content), {
		parse_mode: "MarkdownV2"
	});
	// @ts-expect-error
	await Conversations.create({ chatId, userId, content: response.choices[0].message.content, role: "assistant" });
});

bot.launch();
console.log("Bot is running");

bot.catch(errorHandler);

process.once("SIGINT", () => bot.stop());
process.once("SIGTERM", () => bot.stop());
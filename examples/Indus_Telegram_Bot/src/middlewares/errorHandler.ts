import type { MyContext } from "../context.ts";
import { readFile, writeFile } from "node:fs/promises";

// USE YOUR OWN TELEGRAM ID FOR THIS.
const LOGS_GROUP = "";

const errorHandler = async (error: any, ctx: MyContext)=>{
	await ctx.reply(`Error: ${error.message}`);
	const fileData = readFile("./errors.log", "utf-8");
	const errorLog = `[${new Date().toString().slice(0, 21)}] ${error.message} <${ctx.from?.id}>\n`;
	await writeFile("./errors.log", fileData + errorLog);
	const errorStr = `<u>Error</u>\nName: ${error.name}\nMessage: ${error.message}\nCause: ${error.cause}\nStack: ${error.stack}\n\nChat ID: ${ctx.from?.id}\nTime of Error: ${new Date().toString().slice(0, 21)}`;
	await ctx.telegram.sendMessage(LOGS_GROUP, errorStr, {
		parse_mode: "HTML"
	});
}

export default errorHandler;
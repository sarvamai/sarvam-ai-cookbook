import type { Context } from "telegraf";

interface Session {
	chatId: string
}

export interface MyContext extends Context{
	session: Session
}
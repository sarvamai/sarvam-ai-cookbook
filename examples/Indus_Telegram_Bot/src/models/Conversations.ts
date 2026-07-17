import { model, Schema } from "mongoose";

const conversationSchema = new Schema({
	userId: { type: Number, required: true },
	content: { type: String, required: true },
	role: { type: String, required: true },
	sendingTime: { type: Date, default: Date.now() },
	chatId: { type: String, required: true }
});

export default model("Conversations", conversationSchema);
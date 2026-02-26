import { model, Schema } from "mongoose";

const userSchema = new Schema({
	userId: { type: Number, required: true, unique: true },
	name: { type: String, required: true, unique: true },
	username: String,
	joinedAt: { type: Date, default: Date.now() }
});

export default model("Users", userSchema);
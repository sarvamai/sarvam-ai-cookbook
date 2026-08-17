import { connect } from "mongoose";
import { config } from "dotenv";

config();

const connectToDatabase = ()=>{
	// @ts-expect-error
	connect(process.env.DB_URL).then(()=>{
		console.log("Connected to Database");
	}).catch(error=>{
		console.log("Error Connecting to Database", error);
	});
}

export default connectToDatabase;
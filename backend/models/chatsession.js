import { DataTypes } from "sequelize";
import sequelize from "../config/db.js"; // make sure this path is correct

const ChatSession = sequelize.define("ChatSession", {
  session_id: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  role: {
    type: DataTypes.ENUM("user", "assistant"),
    allowNull: false,
  },
  message: {
    type: DataTypes.TEXT,
    allowNull: false,
  },
});

export default ChatSession;

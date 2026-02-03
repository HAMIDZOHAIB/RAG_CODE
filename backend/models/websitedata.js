import { DataTypes } from "sequelize";
import sequelize from "../config/db.js"; // path from models to config/db.js

const WebsiteData = sequelize.define("WebsiteData", {
  website_id: { type: DataTypes.INTEGER, allowNull: false },
  website_link: { type: DataTypes.STRING, allowNull: false },
  plain_text: { type: DataTypes.TEXT, allowNull: false },
  embedding: { type: DataTypes.ARRAY(DataTypes.FLOAT), allowNull: false },
});

export default WebsiteData;

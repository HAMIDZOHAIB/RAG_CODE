import { DataTypes } from "sequelize";
import sequelize from "../config/db.js"; // path from models to config/db.js

const WebsiteData = sequelize.define("WebsiteData", {
  website_id: { type: DataTypes.INTEGER, allowNull: false },
  website_link: { type: DataTypes.STRING, allowNull: false },
  plain_text: { type: DataTypes.TEXT, allowNull: false },
  embedding: {
    type: "vector(1024)", // raw type for pgvector
    allowNull: false,
  },
});

export default WebsiteData;

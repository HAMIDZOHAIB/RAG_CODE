import { Sequelize } from "sequelize";
import dotenv from "dotenv";

dotenv.config(); // loads .env

// Create a Sequelize instance
const sequelize = new Sequelize(
  process.env.DB_NAME,     // database name
  process.env.DB_USER,     // username
  process.env.DB_PASSWORD, // password
  {
    host: process.env.DB_HOST,
    dialect: "postgres",
    port: process.env.DB_PORT,
    logging: false,
  }
);

export default sequelize;

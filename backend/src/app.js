// backend/src/server.js (or app.js)
import express from "express";
import dotenv from "dotenv";
import cors from "cors";  // ← Add this import
import pool from "../config/db.js";
import websiteDataRouter from "./routes/websiteData.js";
import queryRouter from "./routes/query.js";
import bodyParser from "body-parser";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// CORS Middleware - ADD THIS BEFORE OTHER MIDDLEWARE
app.use(cors({
  origin: 'http://localhost:5173', // Vite default port
  credentials: true,
}));

// Other Middleware
app.use(express.json());
app.use(bodyParser.json({ limit: "50mb" }));

// Routes
app.use("/api/website-data", websiteDataRouter);
app.use("/api/query", queryRouter);

// Root route
app.get("/", (req, res) => {
  res.send("Server is running 🚀");
});

// DB Test route
app.get("/db-test", async (req, res) => {
  try {
    const result = await pool.query("SELECT NOW()");
    res.send(`✅ DB Connected! Current Time: ${result.rows[0].now}`);
  } catch (err) {
    console.error("❌ DB connection error:", err.message);
    res.status(500).send("❌ DB connection failed. Check console for details.");
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
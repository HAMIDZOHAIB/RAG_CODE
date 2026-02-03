// routes/queryRoutes.js
import express from "express";
import { handleQuery, getChatHistory, clearHistory } from "../controllers/queryController.js";

const router = express.Router();

router.post("/", handleQuery);
router.get("/history", getChatHistory); 
router.post("/clear-history", clearHistory);

export default router;
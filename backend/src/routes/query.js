// routes/queryRoutes.js
import express from "express";
import { handleQuery, getChatHistory, clearHistory,exportMcqs   } from "../controllers/queryController.js";

const router = express.Router();

router.post("/", handleQuery);
router.get("/history", getChatHistory); 
router.post("/clear-history", clearHistory);
router.get("/export-mcqs", exportMcqs);
//router.get("/export-sjt", exportSjt);
export default router;